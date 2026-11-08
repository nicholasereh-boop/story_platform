"""Pulling articles in from approved sources, and importing by hand. Imports ALWAYS land in the review queue (pending), never live.

run_source() refuses to fetch unless: imports are switched on (NEWS_IMPORT_ENABLED), the source has an adapter, the rights gate allows
the source, a denylisted publisher has written permission, the daily quota is not used up, the poll interval has passed and the source
is not backing off after failures. It fetches only the feed address staff registered (netguard), parses it, drops duplicates, caps the
number of items, and records every attempt (also skipped ones, with the reason) as a NewsIngestionRun."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit import service as audit

from ..models import NewsArticle, NewsIngestionRun, NewsSource
from ..providers import AdapterError, get_adapter
from . import articles, netguard, policy, rights, sanitize

MAX_BACKOFF_STEPS = 5


def _import_data(item):
    data = {"title": item.title, "standfirst": item.standfirst, "body": item.body, "author_name": item.author,
            "canonical_url": item.canonical_url, "original_url": item.canonical_url}
    if item.published_at:
        data["source_published_at"] = item.published_at
    if item.language:
        data["language"] = item.language
    return data


def _failure_streak(source):
    streak = 0
    for run in source.runs.exclude(status=NewsIngestionRun.Status.SKIPPED).order_by("-started_at")[:MAX_BACKOFF_STEPS + 1]:
        if run.status == NewsIngestionRun.Status.FAILED:
            streak += 1
        else:
            break
    return streak


def skip_reason(source, now, *, force=False):
    """Why this source may not be polled right now, or "" if it may. Pure checks, no network."""
    if not settings.NEWS_IMPORT_ENABLED:
        return "imports_disabled"
    if not source.adapter or get_adapter(source.adapter) is None:
        return "no_adapter"
    if source.source_type == NewsSource.SourceType.METADATA_ONLY:
        return "metadata_only_source"
    decision = rights.evaluate(source, now=now)
    if not decision.allowed:
        return "rights:" + (decision.reasons[0] if decision.reasons else "not_allowed")
    if not decision.full_text:
        return "full_text_not_permitted"
    if policy.source_is_denylisted(source) and decision.record.basis not in policy.PERMISSION_BASES:
        return "publisher_needs_written_permission"
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    used = source.runs.filter(started_at__gte=day_start).exclude(status=NewsIngestionRun.Status.SKIPPED).count()
    if used >= source.daily_request_quota:
        return "daily_quota_reached"
    if not force:
        last = source.runs.exclude(status=NewsIngestionRun.Status.SKIPPED).first()
        if last:
            wait = timedelta(minutes=source.poll_interval_minutes)
            streak = _failure_streak(source)
            if streak:
                wait *= 2 ** min(streak, MAX_BACKOFF_STEPS)
            if now < last.started_at + wait:
                return "backing_off" if streak else "too_soon"
    return ""


def run_source(source, *, now=None, force=False, session=None, resolver=None):
    """Poll one source. Always returns the NewsIngestionRun it recorded; `run.retryable` says whether trying again soon may help."""
    now = now or timezone.now()
    run = NewsIngestionRun(source=source, started_at=now)
    run.retryable = False
    reason = skip_reason(source, now, force=force)
    if reason:
        run.status, run.reason, run.finished_at = NewsIngestionRun.Status.SKIPPED, reason[:60], timezone.now()
        run.save()
        return run
    adapter = get_adapter(source.adapter)
    host = policy.host_of(source.feed_url)
    try:
        payload, http_status = netguard.fetch_bytes(
            source.feed_url, allowed_hosts=[host], max_bytes=settings.NEWS_FEED_MAX_BYTES, timeout=settings.NEWS_FEED_TIMEOUT_SECONDS,
            session=session, **({"resolver": resolver} if resolver else {}),
        )
        run.http_status = http_status
        items = adapter.parse(payload, source)
    except netguard.FetchFailed as exc:
        run.status, run.reason, run.message, run.http_status = NewsIngestionRun.Status.FAILED, exc.code[:60], exc.message[:300], exc.http_status
        run.retryable = exc.retryable
        run.finished_at = timezone.now()
        run.save()
        audit.log(None, "news.ingest_run", source, source_name=source.name, status="failed", reason=exc.code)
        return run
    except AdapterError as exc:
        run.status, run.reason, run.message, run.finished_at = NewsIngestionRun.Status.FAILED, "bad_feed", str(exc)[:300], timezone.now()
        run.save()
        audit.log(None, "news.ingest_run", source, source_name=source.name, status="failed", reason="bad_feed")
        return run

    run.fetched = len(items)
    for item in items[: source.max_items_per_poll]:
        try:
            outcome = _import_item(source, item)
        except Exception as exc:  # one bad item must not stop the rest
            run.errors += 1
            run.message = f"{item.title[:80]}: {exc}"[:300]
            continue
        setattr(run, outcome, getattr(run, outcome) + 1)
    run.status, run.finished_at = NewsIngestionRun.Status.OK, timezone.now()
    run.save()
    if run.created or run.errors:
        audit.log(None, "news.ingest_run", source, source_name=source.name, status="ok", created=run.created, duplicates=run.duplicates, errors=run.errors)
    return run


def _import_item(source, item):
    """Returns the NewsIngestionRun counter this item belongs to: created, duplicates, updated or changed_live."""
    data = _import_data(item)
    existing, how = articles.find_duplicate(source, external_id=item.external_id, canonical_url=item.canonical_url, title=item.title, body=item.body)
    if existing:
        if how == "external_id" and existing.original_hash and existing.original_hash != sanitize.content_hash(item.title, sanitize.clean_body(item.body)):
            if existing.status in (NewsArticle.Status.PUBLISHED, NewsArticle.Status.SCHEDULED):
                return "changed_live"
            if existing.status in (NewsArticle.Status.DRAFT, NewsArticle.Status.PENDING, NewsArticle.Status.REJECTED):
                with transaction.atomic():
                    articles.update_article(existing, None, data, note="updated from source")
                    existing.original_hash = existing.content_hash
                    existing.save(update_fields=["original_hash", "updated_at"])
                return "updated"
        return "duplicates"
    with transaction.atomic():
        article = articles.create_article(None, source, data, imported=True, external_id=item.external_id)
        if sanitize.plain_text(article.body):
            articles.submit(article, None)  # default: waiting for review. Without full text in the feed it stays a draft with blockers.
    return "created"


def import_manual(user, source, data):
    """Staff paste an article they have the right to use. Same dedupe and review queue as feeds. Raises articles.ArticleError."""
    existing, how = articles.find_duplicate(source, canonical_url=data.get("canonical_url", ""), title=data.get("title", ""), body=sanitize.clean_body(data.get("body", "")))
    if existing:
        raise articles.ArticleError(f"This looks like an article you already have (matched by {how.replace('_', ' ')}): #{existing.pk} {existing.title}")
    with transaction.atomic():
        article = articles.create_article(user, source, data, imported=True)
        if sanitize.plain_text(article.body):
            articles.submit(article, user)
    return article


def preview_import(source, data, now=None):
    """What importing this would do, without saving anything: the cleaned text, any duplicate, and the publishing gate's verdict."""
    now = now or timezone.now()
    clean = sanitize.clean_body(data.get("body", ""))
    existing, how = articles.find_duplicate(source, canonical_url=data.get("canonical_url", ""), title=data.get("title", ""), body=clean)
    draft = NewsArticle(source=source, title=data.get("title", ""), body=clean, author_name=data.get("author_name", ""), canonical_url=data.get("canonical_url", ""),
                        original_url=data.get("original_url", "") or data.get("canonical_url", ""), imported=True, article_type=articles._type_for(source),
                        source_published_at=data.get("source_published_at"))
    draft.rights_record = rights.current_record(source, now)
    draft.content_hash = sanitize.content_hash(draft.title, draft.body)
    draft.original_hash = draft.content_hash
    draft.attribution = articles._attribution(draft, now)
    ok, reasons = articles.check_publishable(draft, now)
    return {"title": draft.title, "body": clean, "words": len(sanitize.plain_text(clean).split()), "attribution": draft.attribution,
            "duplicate": {"id": existing.pk, "title": existing.title, "matched_by": how} if existing else None, "can_publish": ok, "blockers": reasons}


def health(source, now=None):
    """The ingestion health line for one source: last result, failure streak, today's use of the quota."""
    now = now or timezone.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last = source.runs.first()
    return {
        "last_status": last.status if last else "", "last_reason": last.reason if last else "", "last_run_at": last.started_at if last else None,
        "failure_streak": _failure_streak(source), "runs_today": source.runs.filter(started_at__gte=day_start).exclude(status="skipped").count(),
        "daily_request_quota": source.daily_request_quota, "next_skip_reason": skip_reason(source, now),
    }

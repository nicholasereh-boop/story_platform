"""Everything that changes an article goes through here, so the rights gate cannot be skipped by a view.

Life of an article:  draft -> pending -> published | scheduled -> published -> withdrawn
                     pending -> rejected         published/scheduled -> quarantined (rights lapsed or disputed) -> pending (restore)
The gate (check_publishable) runs before an article becomes published or scheduled, again when a scheduled one comes due, and again
whenever a published article is edited. Public reads also re-check rights (NewsArticleQuerySet.public)."""
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.utils import unique_slug

from ..models import NewsArticle, NewsCategory, NewsRevision, NewsSource
from . import policy, rights, sanitize

EDITABLE_FIELDS = ("title", "standfirst", "body", "author_name", "category", "language", "is_featured", "is_breaking", "canonical_url", "original_url", "source_published_at")
CACHE_VERSION_KEY = "news:version"


class ArticleError(ValueError):
    """An editorial action that is not allowed in the current state. The message is safe to show to staff."""

    def __init__(self, message, reasons=None):
        super().__init__(message)
        self.reasons = list(reasons or [])


# ---- cache version: one number that every cached public list includes in its key ---------------------------
def cache_version():
    try:
        return cache.get(CACHE_VERSION_KEY) or 1
    except Exception:
        return 1


def bump_cache():
    """Make every cached public list stale at once. incr keeps the number strictly increasing; a missing key restarts from the clock."""
    try:
        try:
            cache.incr(CACHE_VERSION_KEY)
        except ValueError:
            cache.set(CACHE_VERSION_KEY, int(timezone.now().timestamp() * 1000), None)
    except Exception:
        pass


# ---- the gate ----------------------------------------------------------------------------------------------
def check_publishable(article, now=None):
    """(ok, reasons). The one answer to "may this article be shown to the public?"."""
    now = now or timezone.now()
    reasons = []
    source = article.source
    record = article.rights_record
    if record is None:
        reasons.append("no_rights_record")
        decision = rights.evaluate(source, now=now)
        reasons.extend(r for r in decision.reasons if r not in reasons and r != "no_rights_record")
        return False, reasons
    decision = rights.evaluate(source, record=record, now=now)
    if not decision.allowed:
        return False, list(decision.reasons)
    if article.article_type == NewsArticle.ArticleType.METADATA_ONLY:
        reasons.append("metadata_only_article")
    if not article.title.strip():
        reasons.append("title_missing")
    if not sanitize.plain_text(article.body):
        reasons.append("body_missing")
    elif not decision.full_text:
        reasons.append("full_text_not_permitted")
    if not decision.commercial and settings.NEWS_REQUIRE_COMMERCIAL_RIGHTS:
        reasons.append("commercial_use_not_permitted")
    if decision.attribution_required and not article.attribution.strip():
        reasons.append("attribution_missing")
    if article.imported and not decision.modification and article.original_hash and article.content_hash != article.original_hash:
        reasons.append("edits_not_permitted")
    if article.imported and decision.attribution_required and source.source_type != NewsSource.SourceType.ORIGINAL and not (article.original_url or article.canonical_url):
        reasons.append("original_link_missing")
    return not reasons, reasons


def _hash(article):
    return sanitize.content_hash(article.title, article.body)


def _revision(article, action, user, note=""):
    number = (article.revisions.aggregate(n=Max("number"))["n"] or 0) + 1
    return NewsRevision.objects.create(article=article, number=number, action=action, title=article.title, standfirst=article.standfirst, body=article.body, note=note[:300], user=user)


def _attribution(article, now=None):
    return rights.render_attribution(
        article.source, article.rights_record, author=article.author_name, original_url=article.original_url or article.canonical_url,
        published=(article.source_published_at or article.published_at or now or timezone.now()).strftime("%d %B %Y"),
    )


def _apply(article, data):
    for field in EDITABLE_FIELDS:
        if field in data:
            value = data[field]
            if field == "body":
                value = sanitize.clean_body(value)
            setattr(article, field, value)
    article.content_hash = _hash(article)
    article.url_hash = sanitize.url_hash(article.canonical_url)


def find_duplicate(source, *, external_id="", canonical_url="", title="", body="", exclude_pk=None):
    """An existing article that is the same piece: same provider id, or same address, or (as a fallback) same visible content."""
    qs = NewsArticle.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if external_id:
        hit = qs.filter(source=source, external_id=external_id).first()
        if hit:
            return hit, "external_id"
    if canonical_url:
        hit = qs.filter(url_hash=sanitize.url_hash(canonical_url)).first()
        if hit:
            return hit, "canonical_url"
    if title or body:
        hit = qs.filter(content_hash=sanitize.content_hash(title, body)).first()
        if hit:
            return hit, "content"
    return None, ""


@transaction.atomic
def create_article(user, source, data, *, imported=False, external_id=""):
    """A new DRAFT. The rights record is the newest one in force (None if there is none; the gate will then refuse to publish)."""
    article = NewsArticle(source=source, editor=user, imported=imported, external_id=external_id, article_type=_type_for(source))
    _apply(article, data)
    article.slug = unique_slug(NewsArticle, article.title, max_length=230, fallback="article")
    article.rights_record = rights.current_record(source)
    article.original_hash = article.content_hash if imported else ""
    article.attribution = _attribution(article)
    try:
        with transaction.atomic():
            article.save()
    except IntegrityError:
        raise ArticleError("An article with this provider ID already exists for this source.")
    _revision(article, "imported" if imported else "created", user)
    return article


def _type_for(source):
    mapping = {"original": "original", "licensed": "licensed", "open_licensed": "open_licensed", "public_domain": "public_domain", "metadata_only": "metadata_only"}
    return mapping.get(source.source_type, "licensed")


@transaction.atomic
def update_article(article, user, data, note=""):
    if article.status in (NewsArticle.Status.WITHDRAWN, NewsArticle.Status.QUARANTINED):
        raise ArticleError("Restore this article (or create a new one) before editing it.")
    before = article.content_hash
    _apply(article, data)
    article.editor = user
    article.attribution = _attribution(article)
    if article.status in (NewsArticle.Status.PUBLISHED, NewsArticle.Status.SCHEDULED):
        ok, reasons = check_publishable(article)
        if not ok:
            raise ArticleError("This edit would make a live article break the rights rules: " + ", ".join(reasons), reasons)
    article.save()
    if article.content_hash != before or note:
        _revision(article, "edited", user, note)
    bump_cache()
    return article


def _require_state(article, allowed, verb):
    if article.status not in allowed:
        raise ArticleError(f"A {article.get_status_display().lower()} article cannot be {verb}.")


@transaction.atomic
def submit(article, user):
    _require_state(article, (NewsArticle.Status.DRAFT, NewsArticle.Status.REJECTED), "submitted for review")
    if not sanitize.plain_text(article.body) or not article.title.strip():
        raise ArticleError("Add a title and the article text before submitting.")
    article.status = NewsArticle.Status.PENDING
    article.review_note = ""
    article.save(update_fields=["status", "review_note", "updated_at"])
    _revision(article, "submitted", user)
    return article


@transaction.atomic
def publish(article, user, when=None):
    """Approve for the public: now, or at `when` (scheduled). The gate must pass. Refreshes the rights record to the newest one in force."""
    _require_state(article, (NewsArticle.Status.PENDING, NewsArticle.Status.DRAFT, NewsArticle.Status.SCHEDULED), "published")
    now = timezone.now()
    article.rights_record = rights.current_record(article.source, now) or article.rights_record
    article.attribution = _attribution(article, now)
    ok, reasons = check_publishable(article, now)
    if not ok:
        raise ArticleError("Not allowed to publish yet: " + ", ".join(reasons), reasons)
    article.reviewer = user
    if when and when > now:
        article.status = NewsArticle.Status.SCHEDULED
        article.scheduled_for = when
        action = "scheduled"
    else:
        article.status = NewsArticle.Status.PUBLISHED
        article.published_at = now
        article.scheduled_for = None
        action = "published"
    article.save()
    _revision(article, action, user)
    bump_cache()
    return article


@transaction.atomic
def reject(article, user, reason):
    _require_state(article, (NewsArticle.Status.PENDING, NewsArticle.Status.DRAFT), "rejected")
    reason = (reason or "").strip()
    if not reason:
        raise ArticleError("Say why the article is rejected, so the editor can fix it.")
    article.status = NewsArticle.Status.REJECTED
    article.review_note = reason[:300]
    article.reviewer = user
    article.save(update_fields=["status", "review_note", "reviewer", "updated_at"])
    _revision(article, "rejected", user, reason)
    return article


@transaction.atomic
def withdraw(article, user, reason):
    _require_state(article, (NewsArticle.Status.PUBLISHED, NewsArticle.Status.SCHEDULED, NewsArticle.Status.QUARANTINED), "withdrawn")
    reason = (reason or "").strip()
    if not reason:
        raise ArticleError("Say why the article is withdrawn.")
    article.status = NewsArticle.Status.WITHDRAWN
    article.review_note = reason[:300]
    article.reviewer = user
    article.save(update_fields=["status", "review_note", "reviewer", "updated_at"])
    _revision(article, "withdrawn", user, reason)
    bump_cache()
    return article


@transaction.atomic
def restore(article, user):
    """A quarantined or withdrawn article goes back to the review queue (never straight to published)."""
    _require_state(article, (NewsArticle.Status.QUARANTINED, NewsArticle.Status.WITHDRAWN), "restored")
    article.status = NewsArticle.Status.PENDING
    article.quarantine_reason = ""
    article.quarantined_from = ""
    article.review_note = ""
    article.rights_record = rights.current_record(article.source) or article.rights_record
    article.save()
    _revision(article, "restored", user)
    bump_cache()
    return article


def quarantine(article, reason, user=None):
    """Hide an article because its rights lapsed or are disputed. Keeps everything for the audit trail."""
    if article.status not in (NewsArticle.Status.PUBLISHED, NewsArticle.Status.SCHEDULED):
        return False
    with transaction.atomic():
        article.quarantined_from = article.status
        article.status = NewsArticle.Status.QUARANTINED
        article.quarantine_reason = reason[:200]
        article.save(update_fields=["status", "quarantined_from", "quarantine_reason", "updated_at"])
        _revision(article, "quarantined", user, reason)
    return True


def quarantine_source(source, reason):
    """Every live article of a source (rights ended, or the source was suspended)."""
    count = sum(1 for a in NewsArticle.objects.filter(source=source, status__in=("published", "scheduled")) if quarantine(a, reason))
    if count:
        bump_cache()
    return count


def quarantine_record(record, reason):
    """Every live article that was published under a record that has now ended."""
    count = sum(1 for a in NewsArticle.objects.filter(rights_record=record, status__in=("published", "scheduled")).select_related("source") if quarantine(a, reason))
    if count:
        bump_cache()
    return count


def publish_due(now=None):
    """Publish scheduled articles whose time has come, after re-checking their rights. Failing ones are quarantined, not published.
    Safe to call on every request (a cheap indexed query when nothing is due)."""
    now = now or timezone.now()
    published = 0
    for article in NewsArticle.objects.filter(status=NewsArticle.Status.SCHEDULED, scheduled_for__lte=now).select_related("source", "rights_record"):
        ok, reasons = check_publishable(article, now)
        with transaction.atomic():
            if ok:
                article.status = NewsArticle.Status.PUBLISHED
                article.published_at = article.scheduled_for
                article.scheduled_for = None
                article.save(update_fields=["status", "published_at", "scheduled_for", "updated_at"])
                _revision(article, "published", None, "scheduled time reached")
                published += 1
            else:
                quarantine(article, "rights check failed at publish time: " + ", ".join(reasons))
    if published:
        bump_cache()
    return published


def sweep_rights(now=None):
    """Daily safety net: expire ended records, then quarantine any live article whose gate no longer passes. Returns the number quarantined."""
    now = now or timezone.now()
    rights.expire_due_records(now)
    count = 0
    for article in NewsArticle.objects.filter(status__in=("published", "scheduled")).select_related("source", "rights_record"):
        ok, reasons = check_publishable(article, now)
        if not ok and quarantine(article, "rights check failed: " + ", ".join(reasons)):
            count += 1
    if count:
        bump_cache()
    return count


# Register with the rights service so revoking, expiring or suspending anything takes live articles down immediately.
def _on_source_loss(source, reason):
    quarantine_source(source, reason)


def _on_record_loss(record, reason):
    quarantine_record(record, reason)


if _on_source_loss not in rights.LOSS_HANDLERS:
    rights.LOSS_HANDLERS.append(_on_source_loss)
if _on_record_loss not in rights.RECORD_HANDLERS:
    rights.RECORD_HANDLERS.append(_on_record_loss)

__all__ = ["ArticleError", "NewsCategory", "policy"]

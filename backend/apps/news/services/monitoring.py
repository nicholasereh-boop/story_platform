"""What the newsroom should look at: one snapshot of the section's health, and the problems in it.
Used by the staff monitoring endpoint, the hourly Celery task (log lines) and `manage.py news_health` (exit code for cron or uptime checks)."""
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ..models import NewsArticle, NewsComment, NewsRightsRecord, NewsSource, NewsTakedown
from . import ingest

logger = logging.getLogger("apps.news.monitoring")

FAILURE_STREAK_ALERT = 3          # this many failed polls in a row
OVERDUE_SCHEDULED_MINUTES = 5     # a scheduled article still not live this long after its time: the worker is not running
COMPLAINT_ALERT_HOURS = 24        # an open complaint older than this needs a decision
STALE_POLL_FACTOR = 3             # no successful poll for this many poll intervals


def snapshot(now=None):
    now = now or timezone.now()
    counts = {status: NewsArticle.objects.filter(status=status).count() for status in NewsArticle.Status.values}
    overdue = NewsArticle.objects.filter(status="scheduled", scheduled_for__lt=now - timedelta(minutes=OVERDUE_SCHEDULED_MINUTES)).count()
    open_complaints = NewsTakedown.objects.filter(status__in=("open", "on_hold"))
    oldest = open_complaints.order_by("created_at").first()
    ending = NewsRightsRecord.objects.filter(
        status="approved", effective_until__isnull=False, effective_until__gt=now,
        effective_until__lte=now + timedelta(days=settings.NEWS_RIGHTS_WARNING_DAYS), source__approval_state="approved",
    ).select_related("source").order_by("effective_until")
    failing, stale = [], []
    if settings.NEWS_IMPORT_ENABLED:
        feeds = NewsSource.objects.filter(approval_state="approved", is_active=True).exclude(adapter="")
        for source in feeds:
            streak = ingest.health(source, now)["failure_streak"]
            if streak >= FAILURE_STREAK_ALERT:
                failing.append({"source": source.pk, "name": source.name, "failure_streak": streak})
            last_ok = source.runs.filter(status="ok").first()
            limit = timedelta(minutes=source.poll_interval_minutes * STALE_POLL_FACTOR)
            if (last_ok.started_at if last_ok else source.reviewed_at or source.created_at) < now - limit:
                stale.append({"source": source.pk, "name": source.name})
    return {
        "generated_at": now, "articles": counts, "scheduled_overdue": overdue,
        "open_complaints": open_complaints.count(), "oldest_open_complaint_at": oldest.created_at if oldest else None,
        "pending_comments": NewsComment.objects.filter(status="pending").count(),
        "rights_ending_soon": [{"source": r.source.name, "title": r.title, "ends": r.effective_until} for r in ending],
        "failing_sources": failing, "stale_sources": stale,
    }


def alerts(snap):
    """The problems in a snapshot, most serious first: [{level, code, message}]. Empty list = healthy."""
    found = []
    if snap["scheduled_overdue"]:
        found.append(("error", "scheduled_overdue", f"{snap['scheduled_overdue']} scheduled article(s) are overdue. Is the Celery worker and beat running?"))
    if snap["articles"].get("quarantined"):
        found.append(("warning", "quarantined", f"{snap['articles']['quarantined']} article(s) are quarantined and need an editor."))
    oldest = snap["oldest_open_complaint_at"]
    if oldest and oldest < snap["generated_at"] - timedelta(hours=COMPLAINT_ALERT_HOURS):
        found.append(("error", "complaint_overdue", f"{snap['open_complaints']} complaint(s) are open and the oldest is over {COMPLAINT_ALERT_HOURS} hours old."))
    for item in snap["failing_sources"]:
        found.append(("warning", "feed_failing", f"{item['name']}: {item['failure_streak']} failed polls in a row."))
    for item in snap["stale_sources"]:
        found.append(("warning", "feed_stale", f"{item['name']}: no successful poll for a long time."))
    for item in snap["rights_ending_soon"]:
        found.append(("warning", "rights_ending", f"Rights for {item['source']} ({item['title']}) end on {item['ends']:%d %b %Y}. Renew them or the articles will be taken down."))
    return [{"level": level, "code": code, "message": message} for level, code, message in found]


def log_alerts(now=None):
    problems = alerts(snapshot(now))
    for p in problems:
        (logger.error if p["level"] == "error" else logger.warning)("news health: %s: %s", p["code"], p["message"])
    return problems

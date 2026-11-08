"""Celery tasks for News. Registered in config/celery.py beat_schedule. Every task is safe to run twice."""
from celery import shared_task
from django.conf import settings

from .models import NewsSource
from .services import articles, ingest, monitoring


@shared_task
def publish_scheduled():
    """Every minute: publish scheduled articles that came due (their rights are re-checked first)."""
    return articles.publish_due()


@shared_task
def poll_due_sources():
    """Every 15 minutes: queue a poll for each approved, active source with an adapter. Does nothing while NEWS_IMPORT_ENABLED is off."""
    if not (settings.NEWS_ENABLED and settings.NEWS_IMPORT_ENABLED):
        return 0
    ids = list(NewsSource.objects.filter(approval_state="approved", is_active=True).exclude(adapter="").values_list("pk", flat=True))
    for source_id in ids:
        poll_source.delay(source_id)
    return len(ids)


@shared_task(bind=True, max_retries=3)
def poll_source(self, source_id):
    """Poll one source. Network trouble is retried with growing delays (1, 2, 4 minutes); everything else waits for the next scheduled poll,
    and repeated failures back the source off (services/ingest.skip_reason)."""
    source = NewsSource.objects.filter(pk=source_id).first()
    if source is None:
        return "gone"
    run = ingest.run_source(source, force=self.request.retries > 0)
    if run.status == "failed" and run.retryable:
        raise self.retry(countdown=60 * 2 ** self.request.retries)
    return run.status


@shared_task
def rights_maintenance():
    """Daily: expire ended rights records and quarantine every live article whose rights check no longer passes."""
    return articles.sweep_rights()


@shared_task
def monitor():
    """Hourly: write one log line per problem the newsroom should know about (see services/monitoring.py). Returns the number of problems."""
    return len(monitoring.log_alerts())

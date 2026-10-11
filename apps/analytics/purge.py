"""Retention: delete raw page-view events (and visitors) that are too old, keeping every aggregate."""
from datetime import timedelta

from django.conf import settings
from django.db.models import Min
from django.utils import timezone

from .aggregation import aggregate_range, purged_before, set_purged_before, utc_start
from .models import PageViewEvent, Visitor

MIN_RETENTION_DAYS = 35  # more than a full month, so the month and week in progress are always complete in raw data
VISITOR_RETENTION_DAYS = 395  # about 13 months


def retention_days():
    return max(settings.ANALYTICS_RETENTION_DAYS, MIN_RETENTION_DAYS)


def purge(now=None, dry_run=False):
    """Aggregate the days about to be removed, then delete old events and stale visitors. Returns a summary dict."""
    now = now or timezone.now()
    cutoff = (now - timedelta(days=retention_days())).date()  # events before this date's midnight (UTC) go
    old = PageViewEvent.objects.filter(created_at__lt=utc_start(cutoff))
    summary = {"cutoff": cutoff, "events": old.count(), "visitors": 0, "aggregated_days": 0, "dry_run": dry_run}
    stale_visitors = Visitor.objects.filter(last_seen_at__lt=now - timedelta(days=VISITOR_RETENTION_DAYS))
    summary["visitors"] = stale_visitors.count()
    if dry_run:
        return summary

    oldest = old.aggregate(first=Min("created_at"))["first"]
    if oldest is not None:
        # Make sure the numbers for these days (and the weeks/months they belong to) exist BEFORE the raw rows go.
        # (aggregate_range skips anything older than the PREVIOUS purge marker, so earlier results are never overwritten.)
        result = aggregate_range(oldest.date(), cutoff - timedelta(days=1))
        summary["aggregated_days"] = result["days"]
        old.delete()
    stale_visitors.delete()
    if summary["events"] or summary["visitors"]:
        from apps.audit import service as audit  # imported here: keeps this module importable without the audit app

        audit.log(None, "analytics.purge", None, events=summary["events"], visitors=summary["visitors"], cutoff=cutoff.isoformat(), aggregated_days=summary["aggregated_days"])
    previous = purged_before()
    if previous is None or cutoff > previous:
        set_purged_before(cutoff)
    return summary

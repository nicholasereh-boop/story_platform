"""Audit-log retention. Entries older than AUDIT_RETENTION_DAYS (never fewer than 30) are removed, and the removal
itself is recorded as ONE summary entry."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from . import service
from .models import AuditLog

MIN_RETENTION_DAYS = 30


def retention_days():
    return max(int(settings.AUDIT_RETENTION_DAYS), MIN_RETENTION_DAYS)


def purge(now=None, dry_run=False):
    """Remove old entries. Returns {"cutoff", "entries", "dry_run"}."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=retention_days())
    count = AuditLog.objects.filter(created_at__lt=cutoff).count()
    summary = {"cutoff": cutoff.date(), "entries": count, "dry_run": dry_run}
    if dry_run or count == 0:
        return summary
    removed = AuditLog.objects.purge_before(cutoff)
    summary["entries"] = removed
    service.log(None, "audit.purge", None, removed=removed, cutoff=cutoff.date().isoformat(), retention_days=retention_days())
    return summary

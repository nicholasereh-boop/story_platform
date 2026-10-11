"""Celery tasks (schedule in config/celery.py). The same work is available without Celery through the commands
`manage.py aggregate_analytics` and `manage.py purge_analytics`."""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .aggregation import aggregate_range
from .purge import purge


@shared_task
def aggregate_recent():
    """Yesterday and today (plus the weeks/months they belong to). Every 15 minutes, and again just after midnight UTC
    so the previous day, week and month are closed with their final numbers."""
    today = timezone.now().date()
    return aggregate_range(today - timedelta(days=1), today)


@shared_task
def purge_old():
    """Daily: delete raw events past the retention period (aggregating them first)."""
    result = purge()
    return {k: str(v) for k, v in result.items()}

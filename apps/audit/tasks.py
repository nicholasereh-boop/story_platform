from celery import shared_task

from .retention import purge


@shared_task
def purge_old_entries():
    """Monthly (config/celery.py): delete audit entries older than the retention period."""
    result = purge()
    return {k: str(v) for k, v in result.items()}

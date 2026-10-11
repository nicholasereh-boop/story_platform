from celery import shared_task

from .services import publish_due


@shared_task
def publish_scheduled():
    """Run every minute by Celery beat (see config/celery.py)."""
    return publish_due()

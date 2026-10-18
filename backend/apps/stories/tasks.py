from celery import shared_task

from .notifications import send_new_story_emails
from .services import publish_due


@shared_task
def publish_scheduled():
    """Run every minute by Celery beat (see config/celery.py)."""
    return publish_due()


@shared_task
def notify_new_story(story_id):
    """Email one newly published story to every member (once)."""
    return send_new_story_emails(story_id)

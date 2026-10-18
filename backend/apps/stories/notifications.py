"""Emailing a new story to every member. Each story is emailed exactly once, however it was published."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, get_connection
from django.db.models import Q
from django.utils import timezone

from .models import Story

BATCH = 50  # messages sent over one mail connection


def queue_new_story_email(story_id):
    """Hand the sending to Celery. Must never break publishing, so any failure here is swallowed."""
    try:
        from .tasks import notify_new_story

        notify_new_story.delay(story_id)
    except Exception:
        pass


def send_new_story_emails(story_id):
    """Email the story to every active member who has not turned the emails off. Returns how many were sent."""
    # Claim the story first: only one caller can flip notified_at from empty, so nobody is emailed twice.
    claimed = Story.objects.public().filter(pk=story_id, notified_at__isnull=True).update(notified_at=timezone.now())
    if not claimed:
        return 0
    story = Story.objects.get(pk=story_id)
    link = f"{settings.FRONTEND_URL}/stories/{story.slug}"
    subject = f"New on {settings.SITE_NAME}: {story.title}"[:200]
    users = (
        get_user_model().objects.filter(is_active=True)
        .filter(Q(profile__isnull=True) | Q(profile__email_new_stories=True))
        .exclude(email="").exclude(email__iendswith=".invalid")
        .values_list("email", flat=True)
    )
    sent = 0
    connection = get_connection()
    batch = []
    for email in users.iterator():
        body = (
            f"A new story has just been published on {settings.SITE_NAME}.\n\n"
            f"{story.title}\n"
            f"{story.excerpt}\n\n"
            f"Read it here: {link}\n\n"
            f"You get this email because you are a member of {settings.SITE_NAME}. "
            f"You can turn these emails off any time from your account page: {settings.FRONTEND_URL}/account"
        )
        batch.append(EmailMessage(subject, body, None, [email], connection=connection))  # one message per person: addresses stay private
        if len(batch) >= BATCH:
            sent += _flush(connection, batch)
            batch = []
    if batch:
        sent += _flush(connection, batch)
    return sent


def _flush(connection, batch):
    try:
        return connection.send_messages(batch) or 0
    except Exception:  # a mail outage must not crash the worker; the story stays marked as sent
        return 0

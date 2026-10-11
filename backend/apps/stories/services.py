from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from .models import Story, StoryRevision


def publish_due():
    """Publish scheduled stories whose time has come. One UPDATE; safe to call on every request."""
    return Story.objects.filter(status=Story.Status.SCHEDULED, scheduled_at__lte=timezone.now()).update(
        status=Story.Status.PUBLISHED, published_at=F("scheduled_at")
    )


def create_revision(story, user, min_interval_minutes=0):
    """Snapshot the story. Returns the new revision, or None when nothing worth saving.

    Skipped when title, excerpt and content equal the latest revision, or (autosave) when the
    latest revision is younger than `min_interval_minutes`.
    """
    latest = story.revisions.first()  # newest first
    if latest and (latest.title, latest.excerpt, latest.content_json) == (story.title, story.excerpt, story.content_json):
        return None
    if latest and min_interval_minutes and latest.created_at > timezone.now() - timedelta(minutes=min_interval_minutes):
        return None
    return StoryRevision.objects.create(
        story=story,
        revision_number=(latest.revision_number + 1) if latest else 1,
        title=story.title,
        excerpt=story.excerpt,
        content_json=story.content_json,
        created_by=user,
    )

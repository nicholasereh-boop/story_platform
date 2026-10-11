"""Like / unlike with an always-correct Story.like_count."""
from django.db import IntegrityError, transaction

from apps.core.counters import adjust_story_counter

from .models import Like


def like_story(user, story):
    """Idempotent. Returns True if a like was created, False if the reader had already liked the story.

    The unique constraint decides, so two simultaneous requests can never both count: the loser gets an
    IntegrityError, which is swallowed (its savepoint is rolled back) and leaves the counter alone.
    """
    with transaction.atomic():
        try:
            with transaction.atomic():
                Like.objects.create(user=user, story=story)
        except IntegrityError:
            return False
        adjust_story_counter(story.pk, "like_count", +1)
    return True


def unlike_story(user, story):
    """Idempotent. Returns True if a like was removed. The counter changes only when a row really was deleted."""
    with transaction.atomic():
        deleted, _ = Like.objects.filter(user=user, story=story).delete()
        if deleted:
            adjust_story_counter(story.pk, "like_count", -1)
    return bool(deleted)

"""Like / unlike with an always-correct Story.like_count, for logged-in readers AND anonymous visitors.

One person = one like per story, however they arrive. A browser that liked a story as a visitor and later logs in does not
get a second like: the visitor's like is handed over to the account ("claimed"), and the counter does not move.
"""
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.core.counters import adjust_story_counter

from .models import Like


def _create(story, **owner):
    """Insert one like; True if it was created, False if the unique constraint says it already exists."""
    try:
        with transaction.atomic():
            Like.objects.create(story=story, **owner)
    except IntegrityError:
        return False
    adjust_story_counter(story.pk, "like_count", +1)
    return True

def has_liked(user, visitor_id, story):
    """True if this logged-in reader OR this browser (visitor token) has liked the story."""
    who = Q()
    if getattr(user, "is_authenticated", False):
        who |= Q(user=user)
    if visitor_id:
        who |= Q(visitor_id=visitor_id)
    return bool(who) and Like.objects.filter(who, story=story).exists()
def like_story(user, story, visitor_id=None):
    """Logged-in like. Idempotent. Returns True if the story's count went up, False if it was already liked.

    The unique constraints decide, so two simultaneous requests can never both count: the loser gets an IntegrityError,
    which is swallowed (its savepoint is rolled back) and leaves the counter alone.
    """
    with transaction.atomic():
        if Like.objects.filter(user=user, story=story).exists():
            if visitor_id:  # this browser also liked it as a visitor: one person, one like
                dropped, _ = Like.objects.filter(visitor_id=visitor_id, story=story).delete()
                if dropped:
                    adjust_story_counter(story.pk, "like_count", -dropped)
            return False
        if visitor_id:
            try:
                with transaction.atomic():
                    claimed = Like.objects.filter(visitor_id=visitor_id, story=story).update(user=user, visitor_id=None)
            except IntegrityError:
                claimed = 0
            if claimed:
                return False  # already counted when it was made as a visitor
        return _create(story, user=user)


def unlike_story(user, story, visitor_id=None):
    """Logged-in unlike. Idempotent. Removes the account's like and any like this browser made as a visitor."""
    who = Q(user=user)
    if visitor_id:
        who |= Q(visitor_id=visitor_id)
    with transaction.atomic():
        deleted, _ = Like.objects.filter(who, story=story).delete()
        if deleted:
            adjust_story_counter(story.pk, "like_count", -deleted)
    return bool(deleted)


def like_as_visitor(visitor_id, story):
    """Anonymous like. Idempotent: True if the count went up, False if this browser had already liked it."""
    return _create(story, visitor_id=visitor_id)


def unlike_as_visitor(visitor_id, story):
    """Anonymous unlike. Idempotent."""
    with transaction.atomic():
        deleted, _ = Like.objects.filter(visitor_id=visitor_id, story=story).delete()
        if deleted:
            adjust_story_counter(story.pk, "like_count", -deleted)
    return bool(deleted)

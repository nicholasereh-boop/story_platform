"""Comment business rules: moderation mode, status changes and the always-correct Story.comment_count.

Counting rule (one definition, used live AND by `recount_engagement`):
    Story.comment_count = number of APPROVED comments, except replies whose parent is HIDDEN.
(A deleted parent shows as a placeholder, so its approved replies stay visible and counted.)
Every status change computes the change in that number and applies it with ONE atomic UPDATE (F() arithmetic).
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.counters import adjust_story_counter

from .models import Comment, SiteSetting

S = Comment.Status
MODERATION_KEY = "comment_moderation"
MODES = ("off", "approve_first", "approve_first_time")
DEFAULT_MODE = "off"


# ---------------------------------------------------------------- site setting
def get_moderation_mode():
    value = SiteSetting.objects.filter(key=MODERATION_KEY).values_list("value", flat=True).first()
    return value if value in MODES else DEFAULT_MODE


def set_moderation_mode(mode):
    if mode not in MODES:
        raise ValueError(mode)
    SiteSetting.objects.update_or_create(key=MODERATION_KEY, defaults={"value": mode})
    return mode


def initial_status(user):
    """Status a NEW comment gets, from the moderation mode. Staff are never held for review."""
    if user.is_staff:
        return S.APPROVED
    mode = get_moderation_mode()
    if mode == "approve_first":
        return S.PENDING
    if mode == "approve_first_time":
        has_approved = Comment.objects.filter(user=user, status=S.APPROVED).exists()
        return S.APPROVED if has_approved else S.PENDING
    return S.APPROVED


# ---------------------------------------------------------------- counting
def visible_weight(status, *, is_reply, parent_status=None, approved_replies=0):
    """How many to add to Story.comment_count for a comment in `status` (see the module docstring)."""
    if is_reply:
        return 1 if status == S.APPROVED and parent_status != S.HIDDEN else 0
    own = 1 if status == S.APPROVED else 0
    nested = approved_replies if status in (S.APPROVED, S.DELETED) else 0  # replies stay visible under a placeholder
    return own + nested


# ---------------------------------------------------------------- operations
def top_level(comment):
    """Replies are one level deep: a reply to a reply attaches to the top-level comment."""
    return comment.parent if comment.parent_id else comment


def can_reply_to(target):
    """You can reply to an approved comment whose thread is not hidden."""
    if target.status != S.APPROVED:
        return False
    return not (target.parent_id and target.parent.status == S.HIDDEN)


@transaction.atomic
def create_comment(*, user, story, body, reply_to=None):
    parent = top_level(reply_to) if reply_to is not None else None
    comment = Comment.objects.create(story=story, user=user, body=body, parent=parent, status=initial_status(user))
    weight = visible_weight(
        comment.status, is_reply=parent is not None, parent_status=parent.status if parent else None
    )
    adjust_story_counter(story.pk, "comment_count", weight)
    return comment


@transaction.atomic
def set_status(comment, new_status):
    """Move a comment to `new_status` and keep Story.comment_count correct. Returns the updated comment."""
    # Lock the row so two moderators acting at once compute their deltas one after the other.
    locked = Comment.objects.select_for_update().get(pk=comment.pk)
    old_status = locked.status
    if old_status != new_status:
        is_reply = locked.parent_id is not None
        parent_status = None
        replies = 0
        if is_reply:
            parent_status = Comment.objects.filter(pk=locked.parent_id).values_list("status", flat=True).first()
        else:
            replies = Comment.objects.filter(parent=locked, status=S.APPROVED).count()
        kwargs = {"is_reply": is_reply, "parent_status": parent_status, "approved_replies": replies}
        delta = visible_weight(new_status, **kwargs) - visible_weight(old_status, **kwargs)
        locked.status = new_status
        locked.save(update_fields=["status", "updated_at"])
        adjust_story_counter(locked.story_id, "comment_count", delta)
    comment.status = locked.status
    return comment


def edit_window():
    return timedelta(minutes=settings.COMMENT_EDIT_WINDOW_MINUTES)


def edit_deadline(comment):
    return comment.created_at + edit_window()


def within_edit_window(comment):
    return timezone.now() <= edit_deadline(comment)


def edit_comment(comment, body):
    now = timezone.now()
    comment.body = body
    comment.edited_at = now
    comment.save(update_fields=["body", "edited_at", "updated_at"])
    return comment

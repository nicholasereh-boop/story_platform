"""Lesson comments and the comment gate. Reuses the site's text cleaning and spam words, but writes only Academy tables."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.utils import display_name
from apps.comments.text import MAX_BODY, MAX_LINKS, blocked_word, clean_body, count_links

from ..errors import Conflict
from ..models import LessonComment, LessonCommentGate
from . import progression

DUPLICATE_WINDOW = timedelta(hours=1)


def comment_data(comment, viewer):
    return {
        "id": comment.pk, "body": comment.body, "status": comment.status, "created_at": comment.created_at,
        "author": display_name(comment.user), "mine": bool(viewer and viewer.is_authenticated and comment.user_id == viewer.pk),
    }


def visible_comments(lesson, viewer):
    """Approved comments for everyone, plus the viewer's own pending ones. Hidden and deleted comments are never listed."""
    wanted = Q(status=LessonComment.Status.APPROVED)
    if viewer and viewer.is_authenticated:
        wanted |= Q(status=LessonComment.Status.PENDING, user=viewer)
    return lesson.comments.select_related("user").filter(wanted).order_by("created_at", "id")


def validate_body(user, lesson, raw):
    text = clean_body(raw)
    if not text:
        raise serializers.ValidationError({"body": ["Write something first."]})
    if len(text) > MAX_BODY:
        raise serializers.ValidationError({"body": [f"Comments can be at most {MAX_BODY} characters."]})
    if count_links(text) > MAX_LINKS:
        raise serializers.ValidationError({"body": [f"Comments can contain at most {MAX_LINKS} links."]})
    if blocked_word(text):
        raise serializers.ValidationError({"body": ["Your comment contains a word that is not allowed here."]})
    if LessonComment.objects.filter(user=user, lesson=lesson, body=text, created_at__gte=timezone.now() - DUPLICATE_WINDOW).exists():
        raise serializers.ValidationError({"body": ["You already posted that comment. Please do not repeat yourself."]})
    return text


@transaction.atomic
def post_comment(user, lesson, state, raw):
    """Create the comment; when the lesson asks for one, this is also what satisfies the gate (once the watch requirement is met).

    Returns the comment. `state` is this learner's progression state for the lesson (from progression.compute_states).
    """
    text = validate_body(user, lesson, raw)
    gated = state["requires_comment"]
    if gated and not state["watch_met"]:
        # Out of order: the gate only opens after the lesson has been watched (docs/ARCHITECTURE.md state machine).
        raise Conflict("Watch the lesson first. You can comment once enough of the video has been watched.")
    status = LessonComment.Status.PENDING if settings.ACADEMY_COMMENT_MODERATION else LessonComment.Status.APPROVED
    comment = LessonComment.objects.create(lesson=lesson, user=user, body=text, status=status)
    if gated:
        gate, created = LessonCommentGate.objects.select_for_update().get_or_create(learner=user, lesson=lesson, defaults={"comment": comment})
        if not created and not (gate.comment_id and gate.comment.status in progression.ACTIVE_COMMENT_STATUSES):
            gate.comment = comment  # the earlier qualifying comment was removed: this one replaces it
            gate.completed_at = timezone.now()
            gate.save(update_fields=["comment", "completed_at"])
    return comment
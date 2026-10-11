"""Serializers for comments.

PUBLIC output (CommentSerializer) is an allowlist: it never contains an email or a user id. The author is shown by
display name only, and a deleted comment shows a placeholder instead of its text and author.
ADMIN output (AdminCommentSerializer) is for staff only and does include the author's email.
"""
from rest_framework import serializers

from apps.stories.serializers import author_name

from . import services
from .models import Comment, CommentReport
from .text import DELETED_PLACEHOLDER, MAX_BODY, clean_body, spam_problem

S = Comment.Status


def _error(field, message):
    """ValidationError that also fills "detail", which the API envelope uses as its top-level message."""
    return serializers.ValidationError({field: [message], "detail": [message]})


# ---------------------------------------------------------------- public output
class CommentSerializer(serializers.ModelSerializer):
    parent = serializers.IntegerField(source="parent_id", read_only=True)
    body = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    edit_expires_at = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id", "parent", "body", "author", "status", "is_mine", "can_edit", "can_delete",
            "edit_expires_at", "created_at", "edited_at", "replies",
        ]

    def _user(self):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return user if user is not None and user.is_authenticated else None

    def get_body(self, obj):
        return DELETED_PLACEHOLDER if obj.status == S.DELETED else obj.body

    def get_author(self, obj):
        return None if obj.status == S.DELETED else author_name(obj.user)  # display name only, never the email

    def get_is_mine(self, obj):
        user = self._user()
        return bool(user and obj.user_id == user.id)

    def _editable(self, obj):
        return self.get_is_mine(obj) and obj.status in (S.APPROVED, S.PENDING) and services.within_edit_window(obj)

    def get_can_edit(self, obj):
        return self._editable(obj)

    def get_can_delete(self, obj):
        user = self._user()
        return bool(user and obj.status != S.DELETED and (obj.user_id == user.id or user.is_staff))

    def get_edit_expires_at(self, obj):
        return services.edit_deadline(obj).isoformat() if self._editable(obj) else None

    def get_replies(self, obj):
        replies = getattr(obj, "visible_replies", None)  # attached by the list view's Prefetch
        return CommentSerializer(replies, many=True, context=self.context).data if replies else []


# ---------------------------------------------------------------- reader input
class _BodyMixin:
    """Shared body rules: 1-2000 characters of PLAIN text, cleaned, whitespace-only rejected, spam filter v1."""

    exclude_comment_id = None  # set when editing, so a comment is not a "duplicate" of itself

    def validate_body(self, value):
        if len(value) > MAX_BODY:
            raise serializers.ValidationError(f"Comments can be at most {MAX_BODY} characters.")
        text = clean_body(value)
        if not text:
            raise serializers.ValidationError("Please write something before posting.")
        problem = spam_problem(text, self.context["request"].user, self.exclude_comment_id)
        if problem:
            raise serializers.ValidationError(problem)
        return text

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError as exc:
            # Surface the first body message as the envelope's top-level message.
            detail = exc.detail
            if isinstance(detail, dict) and "body" in detail and "detail" not in detail:
                first = detail["body"][0] if isinstance(detail["body"], list) else detail["body"]
                detail["detail"] = [str(first)]
            raise


class CommentCreateSerializer(_BodyMixin, serializers.Serializer):
    body = serializers.CharField(trim_whitespace=False, allow_blank=True, error_messages={"required": "Please write something before posting."})
    parent = serializers.IntegerField(required=False, allow_null=True)


class CommentEditSerializer(_BodyMixin, serializers.Serializer):
    body = serializers.CharField(trim_whitespace=False, allow_blank=True, error_messages={"required": "Please write something before posting."})

    def __init__(self, *args, comment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.exclude_comment_id = comment.pk if comment else None


class ReportSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300, default="")

    def validate_reason(self, value):
        return clean_body(value)


# ---------------------------------------------------------------- admin
class AdminCommentSerializer(serializers.ModelSerializer):
    story = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    parent = serializers.IntegerField(source="parent_id", read_only=True)
    report_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "body", "status", "parent", "story", "author", "report_count", "created_at", "updated_at", "edited_at"]

    def get_story(self, obj):
        return {"id": obj.story_id, "title": obj.story.title, "slug": obj.story.slug}

    def get_author(self, obj):
        return {"display_name": author_name(obj.user), "email": obj.user.email}


class AdminReportSerializer(serializers.ModelSerializer):
    reporter = serializers.SerializerMethodField()

    class Meta:
        model = CommentReport
        fields = ["id", "reason", "created_at", "reporter"]

    def get_reporter(self, obj):
        return {"display_name": author_name(obj.user), "email": obj.user.email}


class AdminStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[S.APPROVED, S.HIDDEN, S.DELETED])

    def validate(self, attrs):
        unknown = set(self.initial_data) - {"status"}
        if unknown:
            raise _error("detail", "Only the status of a comment can be changed.")
        return attrs


class CommentSettingsSerializer(serializers.Serializer):
    comment_moderation = serializers.ChoiceField(choices=list(services.MODES))

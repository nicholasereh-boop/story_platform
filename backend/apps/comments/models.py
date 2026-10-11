from django.conf import settings
from django.db import models


class SiteSetting(models.Model):
    """Tiny key/value store for site-wide settings editable in the admin (currently: comment_moderation)."""

    key = models.CharField(max_length=64, unique=True)
    value = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.key}={self.value}"


class Comment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"  # waiting for a moderator; visible only to its author
        APPROVED = "approved", "Approved"  # visible to everyone
        HIDDEN = "hidden", "Hidden"  # hidden by a moderator (its replies are hidden with it)
        DELETED = "deleted", "Deleted"  # soft-deleted by its author or a moderator; shown as a placeholder if it has replies

    story = models.ForeignKey("stories.Story", on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    body = models.TextField()  # PLAIN TEXT only; the frontend renders it as text, never as HTML
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPROVED)
    # Replies are one level deep: a reply's parent is always a top-level comment.
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["story", "status", "created_at"], name="comment_story_status_idx"),
            models.Index(fields=["status", "created_at"], name="comment_status_created_idx"),
        ]

    def __str__(self):
        return f"Comment {self.pk} ({self.status})"


class CommentReport(models.Model):
    """A reader flags a comment for moderators. One report per reader per comment."""

    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="reports")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_reports")
    reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["comment", "user"], name="report_unique_comment_user")]

    def __str__(self):
        return f"Report on comment {self.comment_id}"

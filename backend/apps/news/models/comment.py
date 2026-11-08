from django.conf import settings
from django.db import models

from .article import NewsArticle


class NewsComment(models.Model):
    """A reader's comment under a News article. News-owned on purpose: story and lesson comments are not touched.
    Flat (no replies), plain text only, logged-in readers only."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"  # waiting for staff; visible to its author only
        APPROVED = "approved", "Approved"
        HIDDEN = "hidden", "Hidden"  # hidden by staff
        DELETED = "deleted", "Deleted"  # removed by its author or by staff

    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="news_comments")
    body = models.TextField()  # PLAIN TEXT; the frontend renders it as text, never as HTML
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.APPROVED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["article", "status", "created_at"], name="news_comment_article_idx")]

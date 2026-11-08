from django.conf import settings
from django.db import models

from .article import NewsArticle


class NewsTakedown(models.Model):
    """A copyright or accuracy complaint about a published article (docs/SOURCE_AND_RIGHTS_POLICY.md, "Onboarding and takedown").
    Credible complaints put the article on hold at once; the article is restored only after the complaint is dismissed."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ON_HOLD = "on_hold", "Article on hold"
        UPHELD = "upheld", "Upheld (article withdrawn)"
        DISMISSED = "dismissed", "Dismissed"

    article = models.ForeignKey(NewsArticle, null=True, blank=True, on_delete=models.SET_NULL, related_name="takedowns")
    article_ref = models.CharField(max_length=300, blank=True)  # what the sender typed (a link or slug), kept even if it matched nothing
    contact_name = models.CharField(max_length=120)
    contact_email = models.EmailField()
    claim = models.CharField(max_length=20, default="copyright")  # copyright | accuracy | other
    message = models.TextField(max_length=4000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    resolution_note = models.CharField(max_length=300, blank=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "-created_at"], name="news_takedown_status_idx")]

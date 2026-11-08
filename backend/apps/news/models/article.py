from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .source import NewsRightsRecord, NewsSource


class NewsCategory(models.Model):
    """The news taxonomy. Independent of the story categories on purpose."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.CharField(max_length=300, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "name", "id"]
        verbose_name_plural = "news categories"

    def __str__(self):
        return self.name


class NewsArticleQuerySet(models.QuerySet):
    def public(self, now=None):
        """What a visitor may see. Status is not enough: the source must still be approved and active and the rights record the
        article was published under must still be in force. Even if the quarantine step has not run yet, a lapsed licence hides the article."""
        now = now or timezone.now()
        return self.filter(
            status=NewsArticle.Status.PUBLISHED,
            published_at__lte=now,
            source__approval_state=NewsSource.Approval.APPROVED,
            source__is_active=True,
            rights_record__status=NewsRightsRecord.Status.APPROVED,
            rights_record__effective_from__lte=now,
        ).filter(Q(rights_record__effective_until__isnull=True) | Q(rights_record__effective_until__gt=now))


class NewsArticle(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Waiting for review"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        QUARANTINED = "quarantined", "Quarantined (rights lapsed or disputed)"

    class ArticleType(models.TextChoices):
        ORIGINAL = "original", "ResourceBoard original"
        LICENSED = "licensed", "Licensed full text"
        OPEN_LICENSED = "open_licensed", "Open-licensed full text"
        PUBLIC_DOMAIN = "public_domain", "Public domain"
        METADATA_ONLY = "metadata_only", "Headline and link only"

    source = models.ForeignKey(NewsSource, on_delete=models.PROTECT, related_name="articles")
    rights_record = models.ForeignKey(NewsRightsRecord, null=True, blank=True, on_delete=models.PROTECT, related_name="articles")
    external_id = models.CharField(max_length=200, blank=True)  # the provider's own ID; unique per source when set
    canonical_url = models.URLField(max_length=700, blank=True)
    original_url = models.URLField(max_length=700, blank=True)  # where readers are sent back to, when the licence needs it
    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True)
    standfirst = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)  # SANITISED html (services/sanitize.py); never stored raw
    author_name = models.CharField(max_length=160, blank=True)
    article_type = models.CharField(max_length=14, choices=ArticleType.choices, default=ArticleType.ORIGINAL)
    language = models.CharField(max_length=8, default="en")
    category = models.ForeignKey(NewsCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="articles")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    attribution = models.CharField(max_length=400, blank=True)
    is_featured = models.BooleanField(default=False)
    is_breaking = models.BooleanField(default=False)
    source_published_at = models.DateTimeField(null=True, blank=True)  # the original publication time, shown as "first published"
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)  # of title + body as they are now
    original_hash = models.CharField(max_length=64, blank=True)  # of title + body as received; a "no changes allowed" licence compares to it
    url_hash = models.CharField(max_length=64, blank=True, db_index=True)  # of the canonical url, for duplicate detection
    imported = models.BooleanField(default=False)
    quarantine_reason = models.CharField(max_length=200, blank=True)
    quarantined_from = models.CharField(max_length=12, blank=True)
    review_note = models.CharField(max_length=300, blank=True)
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NewsArticleQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], condition=~Q(external_id=""), name="news_article_source_external_uniq"),
        ]
        indexes = [
            models.Index(fields=["status", "-published_at"], name="news_article_status_idx"),
            models.Index(fields=["status", "scheduled_for"], name="news_article_sched_idx"),
        ]

    def __str__(self):
        return self.title


class NewsAsset(models.Model):
    """An image or video attached to an article. Its rights are its own: a cleared article text does not clear its pictures."""

    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    class Approval(models.TextChoices):
        PENDING = "pending", "Waiting for clearance"
        CLEARED = "cleared", "Cleared"
        REJECTED = "rejected", "Rejected (omitted)"

    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name="assets")
    kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.IMAGE)
    image = models.ForeignKey("media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")  # a file in OUR library
    source_url = models.URLField(max_length=700, blank=True)  # where it came from (never hot-linked to readers)
    video_id = models.CharField(max_length=11, blank=True)  # YouTube id for kind=video
    alt_text = models.CharField(max_length=300, blank=True)
    caption = models.CharField(max_length=500, blank=True)
    creator = models.CharField(max_length=160, blank=True)
    credit = models.CharField(max_length=300, blank=True)
    licence = models.CharField(max_length=80, blank=True)
    allows_commercial_use = models.BooleanField(default=False)
    allows_modification = models.BooleanField(default=False)
    evidence_url = models.URLField(max_length=500, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    approval_state = models.CharField(max_length=8, choices=Approval.choices, default=Approval.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]

    def is_displayable(self, now=None):
        now = now or timezone.now()
        if self.approval_state != self.Approval.CLEARED or not self.allows_commercial_use:
            return False
        if self.expires_at and self.expires_at <= now:
            return False
        return bool(self.image_id or self.video_id)


class NewsRevision(models.Model):
    """The editorial and import history of an article: what changed, who did it, and why."""

    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    action = models.CharField(max_length=24)  # created, edited, submitted, published, scheduled, rejected, withdrawn, quarantined, restored, imported
    title = models.CharField(max_length=220)
    standfirst = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    note = models.CharField(max_length=300, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number", "-id"]
        unique_together = [("article", "number")]


class NewsViewCount(models.Model):
    """Daily page-view totals for articles whose licence asks for a counter (for example a republication counter the original
    publisher can check). Counts only; no visitor data is stored."""

    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name="view_counts")
    day = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("article", "day")]

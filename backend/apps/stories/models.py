from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import Truncator

from apps.core.utils import unique_slug

from .content import empty_doc, plain_text


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Category, self.name, self, max_length=90)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Tag, self.name, self, max_length=70)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class StoryQuerySet(models.QuerySet):
    def public(self):
        """Stories visitors may see: published, with a publish time that has already passed."""
        return self.filter(status=Story.Status.PUBLISHED, published_at__lte=timezone.now())


class Story(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.TextField(max_length=500, blank=True)
    content_json = models.JSONField(default=empty_doc)  # TipTap JSON, validated by content.clean_content()
    search_text = models.TextField(blank=True, editable=False)  # plain text copy for later search
    cover_image = models.ForeignKey("media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    categories = models.ManyToManyField(Category, blank=True, related_name="stories")
    tags = models.ManyToManyField(Tag, blank=True, related_name="stories")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    seo_title = models.CharField(max_length=70, blank=True)
    seo_description = models.CharField(max_length=200, blank=True)
    # Read-only here; later phases (analytics, likes, comments) keep these up to date.
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)

    objects = StoryQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "stories"
        indexes = [
            models.Index(fields=["status", "published_at"], name="story_status_pub_idx"),
            models.Index(fields=["created_at"], name="story_created_idx"),
            models.Index(fields=["updated_at"], name="story_updated_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Story, self.title, self, max_length=220, fallback="story")
        text = plain_text(self.content_json)
        self.search_text = text[:50000]
        if not self.excerpt:
            self.excerpt = Truncator(text.replace("\n", " ")).chars(200)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class StoryRevision(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="revisions")
    revision_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    excerpt = models.TextField(blank=True)
    content_json = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revision_number"]
        constraints = [
            models.UniqueConstraint(fields=["story", "revision_number"], name="unique_story_revision_number"),
        ]

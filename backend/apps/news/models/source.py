from django.conf import settings
from django.db import models
from django.utils import timezone


class NewsSource(models.Model):
    """Where news comes from. A source is only a candidate until staff approve it AND record rights evidence for it
    (docs/SOURCE_AND_RIGHTS_POLICY.md): an API key, a feed or a public web page does not grant any right to republish."""

    class SourceType(models.TextChoices):
        ORIGINAL = "original", "ResourceBoard original reporting"
        LICENSED = "licensed", "Licensed (written permission or agreement)"
        OPEN_LICENSED = "open_licensed", "Open licence (for example Creative Commons)"
        PUBLIC_DOMAIN = "public_domain", "Verified public domain"
        METADATA_ONLY = "metadata_only", "Headlines and links only"

    class Adapter(models.TextChoices):
        NONE = "", "Manual entry only"
        RSS = "rss", "RSS or Atom feed"

    class Approval(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Approved"
        SUSPENDED = "suspended", "Suspended"
        REJECTED = "rejected", "Rejected"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    source_type = models.CharField(max_length=14, choices=SourceType.choices, default=SourceType.LICENSED)
    website_url = models.URLField(max_length=300, blank=True)
    terms_url = models.URLField(max_length=300, blank=True)  # the licence / republication terms page
    adapter = models.CharField(max_length=8, choices=Adapter.choices, blank=True, default="")
    feed_url = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=False)  # a switch on top of approval: approved but paused sources are not polled
    approval_state = models.CharField(max_length=10, choices=Approval.choices, default=Approval.PENDING)
    # The ceiling for everything this source publishes: a rights record can narrow it, never widen it.
    allows_full_text = models.BooleanField(default=False)
    allows_commercial_use = models.BooleanField(default=False)
    attribution_template = models.CharField(max_length=400, blank=True)  # tokens: {author} {source} {original_url} {licence} {published}
    evidence_ref = models.CharField(max_length=300, blank=True)  # where the signed agreement / saved terms are kept
    renewal_contact = models.CharField(max_length=200, blank=True)
    poll_interval_minutes = models.PositiveIntegerField(default=60)
    max_items_per_poll = models.PositiveIntegerField(default=20)
    daily_request_quota = models.PositiveIntegerField(default=24)
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["approval_state", "is_active"], name="news_source_state_idx")]

    def __str__(self):
        return self.name


class NewsRightsRecord(models.Model):
    """What a source (or a specific licence version) lets ResourceBoard do, with the evidence. Text rights and media rights are
    separate: this record covers article TEXT; every NewsAsset carries its own rights. Approved records are never edited in
    place; a changed licence is a new record, and an old one is revoked or simply expires."""

    class Basis(models.TextChoices):
        ORIGINAL = "original", "ResourceBoard's own work"
        WRITTEN_PERMISSION = "written_permission", "Written permission"
        SYNDICATION = "syndication_agreement", "Syndication agreement"
        OPEN_LICENCE = "open_licence", "Open licence"
        PUBLIC_DOMAIN = "public_domain", "Public domain"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    source = models.ForeignKey(NewsSource, on_delete=models.PROTECT, related_name="rights_records")
    title = models.CharField(max_length=160)
    licence = models.CharField(max_length=80)  # e.g. "CC BY-ND 4.0"
    licence_version = models.CharField(max_length=20, blank=True)
    licence_url = models.URLField(max_length=300, blank=True)
    basis = models.CharField(max_length=24, choices=Basis.choices)
    allows_full_text = models.BooleanField(default=False)
    allows_commercial_use = models.BooleanField(default=False)  # needed to show the article next to advertising
    allows_modification = models.BooleanField(default=False)  # editing or translating the text (false for "no derivatives")
    requires_attribution = models.BooleanField(default=True)
    requires_counter = models.BooleanField(default=False)  # e.g. a page-view counter the original publisher asks for
    allows_caching = models.BooleanField(default=True)
    allows_archive = models.BooleanField(default=True)
    retention_days = models.PositiveIntegerField(null=True, blank=True)  # null = no limit
    restrictions = models.TextField(blank=True)
    effective_from = models.DateTimeField(default=timezone.now)
    effective_until = models.DateTimeField(null=True, blank=True)
    evidence_url = models.URLField(max_length=500, blank=True)
    evidence_note = models.TextField(blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from", "-id"]
        indexes = [models.Index(fields=["source", "status"], name="news_rights_source_idx")]

    def __str__(self):
        return f"{self.source_id}: {self.title}"

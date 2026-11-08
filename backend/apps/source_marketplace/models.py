"""Source-code marketplace models. Everything here is NEW and separate from Story and the media library."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from .storage import private_storage

KINDS = (("frontend", "Frontend"), ("backend", "Backend"))


class Technology(models.Model):
    """A technology tag such as "React" or "Django". Created on demand from what sellers type."""

    name = models.CharField(max_length=30)
    slug = models.SlugField(max_length=40, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "technologies"

    def __str__(self):
        return self.name


class SourceProject(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Waiting for review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="source_projects")
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=90, unique=True)
    summary = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)  # plain text, always rendered as text
    notes = models.TextField(blank=True)  # install / usage notes, plain text
    technologies = models.ManyToManyField(Technology, blank=True, related_name="projects")
    youtube_id = models.CharField(max_length=11, blank=True)  # the 11-character id only, never a stored URL
    # Three optional description videos (YouTube ids only): `youtube_id` above is the one about BOTH parts (overview).
    frontend_video_id = models.CharField(max_length=11, blank=True)  # describes the frontend
    backend_video_id = models.CharField(max_length=11, blank=True)  # describes the backend
    # Prices in MAJOR units of `currency` (for example 49.00 USD). 0 = free (never allowed for backend code, see settings). The server reads them at checkout time.
    frontend_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    backend_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    review_note = models.CharField(max_length=500, blank=True)
    # The seller's confirmation that they own the code or may distribute it. Required before submitting.
    rights_confirmed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-id"]
        indexes = [models.Index(fields=["status", "-published_at"])]

    def __str__(self):
        return self.title

    def price_for(self, kind):
        return self.frontend_price if kind == "frontend" else self.backend_price

    @property
    def is_public(self):
        return self.status == self.Status.PUBLISHED


def package_path(instance, filename):
    return f"packages/{instance.project_id}/{instance.kind}-{uuid.uuid4().hex}.zip"


class SourcePackage(models.Model):
    """One downloadable ZIP of a project: its frontend or its backend (one active file per kind)."""

    class Source(models.TextChoices):
        UPLOAD = "upload", "ZIP upload"
        GITHUB = "github", "GitHub import"

    project = models.ForeignKey(SourceProject, on_delete=models.CASCADE, related_name="packages")
    kind = models.CharField(max_length=10, choices=KINDS)
    version = models.CharField(max_length=30, default="1.0.0")
    file = models.FileField(storage=private_storage, upload_to=package_path, max_length=255)
    original_name = models.CharField(max_length=120, blank=True)  # display text only
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    file_count = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.UPLOAD)
    source_ref = models.CharField(max_length=200, blank=True)  # "owner/repo@ref" for imports. Never a token.
    scan_report = models.JSONField(default=dict, blank=True)  # what the upload check removed or flagged
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "kind"], name="source_package_one_per_kind")]

    def __str__(self):
        return f"{self.project_id}/{self.kind} v{self.version}"


class SourcePurchase(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Paid"
        FAILED = "failed", "Failed"

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="source_purchases")
    package = models.ForeignKey(SourcePackage, on_delete=models.PROTECT, related_name="purchases")  # sold packages are never deleted
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # what the server asked Paystack to CHARGE, major units
    amount_minor = models.BigIntegerField()  # the same in kobo/cents: the exact figure Paystack must confirm
    currency = models.CharField(max_length=3)  # the currency Paystack charges (naira by default)
    list_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # the dollar price the buyer saw
    list_currency = models.CharField(max_length=3, blank=True)
    fx_rate = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)  # list currency -> charge currency
    reference = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    gateway_status = models.CharField(max_length=40, blank=True)  # Paystack's own word, for support
    failure_reason = models.CharField(max_length=60, blank=True)
    paystack_transaction_id = models.CharField(max_length=40, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["buyer", "package", "status"])]

    def __str__(self):
        return self.reference


class PaymentEvent(models.Model):
    """One processed Paystack webhook delivery. The hash of the exact body makes retries harmless."""

    payload_hash = models.CharField(max_length=64, unique=True)
    event = models.CharField(max_length=60)
    reference = models.CharField(max_length=64, blank=True)
    outcome = models.CharField(max_length=40, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)


class ProjectScreenshot(models.Model):
    project = models.ForeignKey(SourceProject, on_delete=models.CASCADE, related_name="screenshots")
    file = models.FileField(upload_to="marketplace/screenshots/%Y/%m/")  # public images, re-encoded by the media checker
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    alt_text = models.CharField(max_length=300, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]


class SourceDownload(models.Model):
    """Audit record: who downloaded which package, and on what basis."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    package = models.ForeignKey(SourcePackage, on_delete=models.CASCADE, related_name="downloads")
    purchase = models.ForeignKey(SourcePurchase, null=True, blank=True, on_delete=models.SET_NULL, related_name="downloads")
    basis = models.CharField(max_length=10)  # free | purchase | owner | staff
    ip_hash = models.CharField(max_length=64, blank=True)  # keyed hash, never the address
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

"""Video tools models. New tables only; nothing here touches stories, media or accounts."""
import uuid

from django.conf import settings
from django.db import models

from .services.storage import private_storage
from .services.url_validation import LABELS


class ProviderCapability(models.Model):
    """Staff switch for ONE provider. A provider can only download when (1) a reviewed adapter exists in code/config,
    (2) it reports itself configured, AND (3) this row says enabled. Missing row = disabled."""

    provider = models.CharField(max_length=20, unique=True, choices=sorted(LABELS.items()))
    download_enabled = models.BooleanField(default=False)
    method_note = models.TextField(blank=True, help_text="The permitted download method this integration uses, and where its terms were reviewed.")
    terms_reviewed_at = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "provider capabilities"

    def __str__(self):
        return f"{self.provider} ({'on' if self.download_enabled else 'off'})"


class DownloadJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Ready"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # not guessable, not sequential
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="video_jobs")
    provider = models.CharField(max_length=20)
    content_id = models.CharField(max_length=80)
    # The canonical link (rebuilt from the id by the validator), never the raw text the person pasted: tracking
    # parameters and anything odd in the pasted link are not stored.
    source_url = models.CharField(max_length=300)
    format_key = models.CharField(max_length=20, default="mp4")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED, db_index=True)
    error_code = models.CharField(max_length=40, blank=True)
    error_message = models.CharField(max_length=300, blank=True)
    authorization_confirmed_at = models.DateTimeField()  # "I own this video or have permission" was ticked
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["requester", "status"]), models.Index(fields=["created_at"])]

    def __str__(self):
        return f"{self.provider}:{self.content_id} [{self.status}]"


def artifact_path(instance, filename):
    return f"downloads/{instance.job_id}/{uuid.uuid4().hex}.bin"


class DownloadArtifact(models.Model):
    job = models.OneToOneField(DownloadJob, on_delete=models.CASCADE, related_name="artifact")
    file = models.FileField(storage=private_storage, upload_to=artifact_path, max_length=255)
    filename = models.CharField(max_length=120)  # the name offered to the person, already made safe
    content_type = models.CharField(max_length=100, default="application/octet-stream")
    size_bytes = models.PositiveBigIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

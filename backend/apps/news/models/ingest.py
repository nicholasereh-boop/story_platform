from django.db import models

from .source import NewsSource


class NewsIngestionRun(models.Model):
    """One attempt to poll a source's feed (or a skipped attempt, with the reason). The newsroom's "ingestion health" is built from these."""

    class Status(models.TextChoices):
        OK = "ok", "Completed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=8, choices=Status.choices)
    reason = models.CharField(max_length=60, blank=True)  # skipped / failed: a stable code such as daily_quota_reached
    message = models.CharField(max_length=300, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    fetched = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    changed_live = models.PositiveIntegerField(default=0)  # upstream changed an article that is already live: left alone, needs an editor's eyes
    errors = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [models.Index(fields=["source", "-started_at"], name="news_run_source_idx")]

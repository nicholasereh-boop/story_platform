"""Callable cleanup helper for management commands or scheduled tasks."""
from .models import DownloadArtifact, DownloadJob
from django.utils import timezone


def cleanup_expired_artifacts():
    now = timezone.now()
    count = 0
    for artifact in DownloadArtifact.objects.filter(expires_at__lte=now, deleted_at__isnull=True).iterator():
        if artifact.file:
            artifact.file.delete(save=False)
        artifact.deleted_at = now
        artifact.save(update_fields=["deleted_at"])
        DownloadJob.objects.filter(pk=artifact.job_id).exclude(status=DownloadJob.Status.CANCELLED).update(
            status=DownloadJob.Status.EXPIRED
        )
        count += 1
    return count

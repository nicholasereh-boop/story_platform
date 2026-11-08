"""The life of a download job: request -> queued -> processing -> done (file kept for a while) -> expired / deleted."""
import logging
import os
import re
import tempfile
from datetime import timedelta

from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.utils import timezone

from ..models import DownloadArtifact, DownloadJob
from . import providers

logger = logging.getLogger(__name__)
ACTIVE = (DownloadJob.Status.QUEUED, DownloadJob.Status.PROCESSING)


class JobRefused(Exception):
    """The request cannot become a job. `code` and `message` are safe to show."""

    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def safe_filename(name, fallback="video.mp4"):
    name = os.path.basename(str(name or "").replace("\\", "/"))
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")[:100]
    return name or fallback


def create_job(user, parsed, format_key, confirmed_at):
    """Apply every rule, create the job and return it. Raises JobRefused."""
    cap = providers.capability_for(parsed.provider)
    if not cap.available:
        raise JobRefused("provider_unavailable", cap.reason, 422)
    valid = {f["key"] for f in cap.formats}
    format_key = format_key or next(iter(valid), "")
    if format_key not in valid:
        raise JobRefused("bad_format", "That format is not available for this provider.")
    if parsed.needs_resolution:
        raise JobRefused("short_link", "That is a shortened link. Open it in your browser and paste the full address of the video.")
    with transaction.atomic():
        mine = DownloadJob.objects.select_for_update().filter(requester=user)
        if mine.filter(status__in=ACTIVE).count() >= settings.VIDEO_TOOLS_MAX_ACTIVE_JOBS:
            raise JobRefused("too_many_active", "You already have downloads in progress. Wait for them to finish.", 429)
        since = timezone.now() - timedelta(hours=24)
        if mine.filter(created_at__gte=since).count() >= settings.VIDEO_TOOLS_MAX_JOBS_PER_DAY:
            raise JobRefused("daily_limit", "You have reached today's download limit. Try again tomorrow.", 429)
        return DownloadJob.objects.create(
            requester=user, provider=parsed.provider, content_id=parsed.content_id, source_url=parsed.canonical_url,
            format_key=format_key, authorization_confirmed_at=confirmed_at,
        )


def enqueue(job):
    """Hand the job to Celery (or run it right here when VIDEO_TOOLS_RUN_INLINE is on: development and tests)."""
    if settings.VIDEO_TOOLS_RUN_INLINE:
        run_job(job.pk)
        return
    try:
        from ..tasks import process_download_job

        process_download_job.delay(str(job.pk))
    except Exception:
        logger.error("Could not queue video job %s", job.pk)
        fail(job.pk, "queue_unavailable", "The download service is busy. Please try again in a few minutes.")


def fail(job_id, code, message):
    DownloadJob.objects.filter(pk=job_id, status__in=ACTIVE).update(
        status=DownloadJob.Status.FAILED, error_code=code[:40], error_message=message[:300], finished_at=timezone.now())


def run_job(job_id):
    """Process one job. Safe to call twice: only one caller can move it from queued to processing."""
    claimed = DownloadJob.objects.filter(pk=job_id, status=DownloadJob.Status.QUEUED).update(
        status=DownloadJob.Status.PROCESSING, started_at=timezone.now())
    if not claimed:
        return None
    job = DownloadJob.objects.get(pk=job_id)
    adapter = providers.get_adapter(job.provider)
    cap = providers.capability_for(job.provider)  # re-checked: staff may have switched the provider off meanwhile
    if adapter is None or not cap.available:
        fail(job_id, "provider_unavailable", cap.reason or "Downloads for this provider are not available.")
        return DownloadJob.objects.get(pk=job_id)
    with tempfile.TemporaryDirectory(prefix="videojob-") as workdir:
        try:
            result = adapter.fetch(job, job.format_key, workdir)
            path = os.path.realpath(result.path)
            if not path.startswith(os.path.realpath(workdir) + os.sep) or not os.path.isfile(path):
                raise providers.AdapterError("The download could not be prepared.", "bad_result")
            size = os.path.getsize(path)
            if size <= 0 or size > settings.VIDEO_TOOLS_MAX_FILE_BYTES:
                raise providers.AdapterError("The file is empty or larger than the allowed size.", "bad_size")
            if DownloadJob.objects.filter(pk=job_id, status=DownloadJob.Status.CANCELLED).exists():
                return DownloadJob.objects.get(pk=job_id)  # cancelled while working: the output is discarded with the temp folder
            artifact = DownloadArtifact(
                job=job, filename=safe_filename(result.filename), content_type=str(result.content_type)[:100], size_bytes=size,
                expires_at=timezone.now() + timedelta(hours=settings.VIDEO_TOOLS_RETENTION_HOURS),
            )
            with open(path, "rb") as handle:
                artifact.file.save("file.bin", File(handle), save=False)
            artifact.save()
            DownloadJob.objects.filter(pk=job_id, status=DownloadJob.Status.PROCESSING).update(
                status=DownloadJob.Status.DONE, finished_at=timezone.now())
        except providers.AdapterError as exc:
            fail(job_id, exc.code, exc.message)
        except Exception as exc:  # fetch helpers raise FetchFailed(message, code); anything else is a bug we must not leak
            message = getattr(exc, "message", None)
            if message:
                fail(job_id, getattr(exc, "code", "failed"), message)
            else:
                logger.exception("Video job %s (%s) crashed", job_id, job.provider)  # no URL in the log line
                fail(job_id, "unexpected", "Something went wrong while preparing the download.")
    return DownloadJob.objects.get(pk=job_id)


def remove_artifact_file(artifact):
    name = artifact.file.name if artifact.file else None
    if name:
        try:
            artifact.file.storage.delete(name)
        except Exception:
            logger.warning("Could not delete a download file for job %s", artifact.job_id)


def cancel_or_remove(job):
    """DELETE semantics: queued/processing -> cancelled; finished -> the file is deleted now."""
    S = DownloadJob.Status
    if job.status in ACTIVE:
        DownloadJob.objects.filter(pk=job.pk, status__in=ACTIVE).update(status=S.CANCELLED, finished_at=timezone.now())
        return "cancelled"
    artifact = getattr(job, "artifact", None)
    if artifact is not None and not artifact.deleted_at:
        remove_artifact_file(artifact)
        artifact.deleted_at = timezone.now()
        artifact.save(update_fields=["deleted_at"])
        DownloadJob.objects.filter(pk=job.pk).update(status=S.EXPIRED)
        return "removed"
    return "nothing"


def cleanup(now=None):
    """Expire finished files, fail stuck jobs, and forget old job rows. Run every few minutes (Celery beat or cron)."""
    now = now or timezone.now()
    S = DownloadJob.Status
    removed = 0
    for artifact in DownloadArtifact.objects.filter(expires_at__lte=now, deleted_at__isnull=True).select_related("job"):
        remove_artifact_file(artifact)
        artifact.deleted_at = now
        artifact.save(update_fields=["deleted_at"])
        DownloadJob.objects.filter(pk=artifact.job_id, status=S.DONE).update(status=S.EXPIRED)
        removed += 1
    stuck = DownloadJob.objects.filter(status__in=ACTIVE, created_at__lte=now - timedelta(seconds=settings.VIDEO_TOOLS_TIMEOUT_SECONDS * 2)).update(
        status=S.FAILED, error_code="timeout", error_message="The download took too long and was stopped.", finished_at=now)
    old = DownloadJob.objects.filter(created_at__lte=now - timedelta(days=settings.VIDEO_TOOLS_JOB_RETENTION_DAYS)).exclude(status__in=ACTIVE)
    forgotten = 0
    for job in old:
        art = getattr(job, "artifact", None)
        if art is not None and not art.deleted_at:
            remove_artifact_file(art)
        job.delete()
        forgotten += 1
    return {"files_removed": removed, "stuck_failed": stuck, "jobs_forgotten": forgotten}

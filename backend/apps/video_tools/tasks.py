from celery import shared_task

from .services import download_jobs


@shared_task(name="apps.video_tools.tasks.process_download_job", soft_time_limit=600, time_limit=660)
def process_download_job(job_id):
    download_jobs.run_job(job_id)


@shared_task(name="apps.video_tools.tasks.cleanup_expired_downloads")
def cleanup_expired_downloads():
    return download_jobs.cleanup()

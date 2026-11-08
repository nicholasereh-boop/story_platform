from django.core.management.base import BaseCommand

from apps.video_tools.services import download_jobs


class Command(BaseCommand):
    help = "Delete expired download files, fail stuck jobs and forget old job records (run every few minutes)."

    def handle(self, *args, **options):
        result = download_jobs.cleanup()
        self.stdout.write(", ".join(f"{k}={v}" for k, v in result.items()))

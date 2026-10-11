from django.core.management.base import BaseCommand

from apps.stories.services import publish_due


class Command(BaseCommand):
    help = "Publish scheduled stories that are due (same job as the Celery task)."

    def handle(self, *args, **options):
        self.stdout.write(f"Published {publish_due()} stories.")

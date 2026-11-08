"""python manage.py news_health : prints the News health summary. Exit code 1 when there is an error-level problem, so cron or an
uptime checker can alert on it."""
from django.core.management.base import BaseCommand

from apps.news.services import monitoring


class Command(BaseCommand):
    help = "Print the News health summary; exit with code 1 if something needs urgent attention."

    def handle(self, *args, **options):
        snap = monitoring.snapshot()
        self.stdout.write(f"Articles: {snap['articles']}")
        self.stdout.write(f"Open complaints: {snap['open_complaints']}  Pending comments: {snap['pending_comments']}")
        problems = monitoring.alerts(snap)
        for p in problems:
            self.stdout.write(f"[{p['level'].upper()}] {p['message']}")
        if not problems:
            self.stdout.write("All good.")
        if any(p["level"] == "error" for p in problems):
            raise SystemExit(1)

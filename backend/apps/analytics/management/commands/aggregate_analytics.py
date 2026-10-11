from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.aggregation import aggregate_range


def _date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise CommandError(f"'{value}' is not a date. Use YYYY-MM-DD.")


class Command(BaseCommand):
    help = (
        "Rebuild daily/weekly/monthly analytics from the raw events. Safe to run any number of times. "
        "Default range: yesterday and today (UTC)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="start", help="first day, YYYY-MM-DD")
        parser.add_argument("--to", dest="end", help="last day, YYYY-MM-DD (default: today)")

    def handle(self, *args, **options):
        today = timezone.now().date()
        end = _date(options["end"]) if options["end"] else today
        start = _date(options["start"]) if options["start"] else end - timedelta(days=1)
        if start > end:
            raise CommandError("--from must not be after --to.")
        summary = aggregate_range(start, end)
        self.stdout.write(
            self.style.SUCCESS(
                f"Aggregated {summary['days']} day(s) and {summary['periods']} week/month row(s) for {start} to {end}."
            )
        )
        if summary["skipped"]:
            self.stdout.write(
                f"Skipped {summary['skipped']} day/period row(s) older than the retention horizon (their raw events were purged; "
                "the stored numbers are kept)."
            )

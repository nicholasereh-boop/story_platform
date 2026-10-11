from django.core.management.base import BaseCommand

from apps.analytics.purge import purge, retention_days


class Command(BaseCommand):
    help = (
        "Delete raw page-view events older than ANALYTICS_RETENTION_DAYS (minimum 35) and visitors unseen for 13 months. "
        "The affected days, weeks and months are aggregated first, and every aggregate is kept."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="only report what would be deleted")

    def handle(self, *args, **options):
        result = purge(dry_run=options["dry_run"])
        verb = "Would delete" if options["dry_run"] else "Deleted"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {result['events']} event(s) before {result['cutoff']} (retention {retention_days()} days) "
                f"and {result['visitors']} stale visitor(s)."
            )
        )
        if result["aggregated_days"]:
            self.stdout.write(f"Aggregated {result['aggregated_days']} day(s) first so no numbers are lost.")

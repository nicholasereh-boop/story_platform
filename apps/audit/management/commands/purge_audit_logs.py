from django.core.management.base import BaseCommand

from apps.audit.retention import purge, retention_days


class Command(BaseCommand):
    help = "Delete audit entries older than AUDIT_RETENTION_DAYS (minimum 30). The purge is recorded as one summary entry."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="only report how many entries would be deleted")

    def handle(self, *args, **options):
        result = purge(dry_run=options["dry_run"])
        verb = "Would delete" if options["dry_run"] else "Deleted"
        self.stdout.write(
            self.style.SUCCESS(f"{verb} {result['entries']} audit entr(y/ies) before {result['cutoff']} (retention {retention_days()} days).")
        )

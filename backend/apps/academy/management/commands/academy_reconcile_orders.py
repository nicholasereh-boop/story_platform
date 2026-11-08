"""Settle Academy orders that were paid but never confirmed (for example the learner closed the tab before returning from
Paystack, and the webhook did not reach this site). Safe to run as often as you like (for example every 10 minutes from cron):
each pending order is checked with Paystack from the server and applied exactly like a normal verification.

    python manage.py academy_reconcile_orders [--days 3] [--min-age-minutes 2]
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit import service as audit

from ...models import CourseOrder
from ...services import payments


class Command(BaseCommand):
    help = "Ask Paystack about recent pending Academy orders and grant access for the ones that were really paid."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=3, help="How far back to look (default 3 days).")
        parser.add_argument("--min-age-minutes", type=int, default=2, help="Leave very new orders alone (default 2 minutes).")

    def handle(self, *args, **options):
        now = timezone.now()
        pending = CourseOrder.objects.filter(
            status=CourseOrder.Status.PENDING,
            created_at__gte=now - timedelta(days=options["days"]),
            created_at__lte=now - timedelta(minutes=options["min_age_minutes"]),
        ).select_related("course", "learner")
        counts = {"paid": 0, "failed": 0, "pending": 0, "errors": 0}
        try:
            client = payments.get_client()
        except payments.PaystackError as exc:
            self.stderr.write(f"Cannot reach Paystack: {exc.message}")
            return
        for order in pending:
            try:
                order, outcome = payments.verify_and_fulfil(order, client)
            except payments.PaystackError:
                counts["errors"] += 1
                continue
            if outcome == "paid":
                audit.log(None, "academy.purchase", order, actor=order.learner, course=order.course.title, amount=str(order.amount),
                          currency=order.currency, via="reconcile")
            counts[outcome if outcome in counts else "pending"] += 1
        self.stdout.write(f"Academy orders checked: {sum(counts.values())} (paid {counts['paid']}, failed {counts['failed']}, still pending {counts['pending']}, errors {counts['errors']})")
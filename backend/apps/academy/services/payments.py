"""Paying for a paid course (docs/ARCHITECTURE.md: Paystack, server-side verification, webhook idempotency).

Reuses the marketplace's Paystack client, signature check, amount check and dollar-to-naira conversion (imported, never copied
or changed); only the records are the Academy's own (CourseOrder, CourseEntitlement). The price is read from the database, the
payment is confirmed by asking Paystack from the server, and access is granted only after that confirmation matches exactly.
"""
import logging
import secrets

from django.db import transaction
from django.utils import timezone

from apps.source_marketplace.services import fx
from apps.source_marketplace.services import payments as gateway

from ..models import CourseEntitlement, CourseOrder, Enrollment

logger = logging.getLogger(__name__)

RateUnavailable = fx.RateUnavailable
PaystackError = gateway.PaystackError


def new_reference():
    """Unguessable and different from the marketplace's references, so the two sites never mix up a payment."""
    return f"rbac_{secrets.token_hex(16)}"


def get_client():
    return gateway.get_client()  # looked up at call time (and refuses with 503 when no secret key is configured)


def grant_access(learner, course, *, source, order=None, granted_by=None, note="", expires_at=None):
    """Give `learner` access to `course` and enrol them. Idempotent: there is never more than one active entitlement.

    Returns (entitlement, created).
    """
    entitlement = CourseEntitlement.objects.filter(learner=learner, course=course, status=CourseEntitlement.Status.ACTIVE).first()
    created = entitlement is None
    if created:
        entitlement = CourseEntitlement.objects.create(
            learner=learner, course=course, source=source, order=order, granted_by=granted_by, note=note[:200], expires_at=expires_at,
        )
    enrollment, made = Enrollment.objects.get_or_create(learner=learner, course=course, defaults={"source": source})
    if not made and (enrollment.status != Enrollment.Status.ACTIVE or enrollment.source == Enrollment.Source.FREE):
        enrollment.status = Enrollment.Status.ACTIVE
        enrollment.source = source
        enrollment.save(update_fields=["status", "source"])
    return entitlement, created


def revoke_access(learner, course):
    """End the learner's active entitlement (progress and enrolment are kept). Returns how many were revoked."""
    return CourseEntitlement.objects.filter(learner=learner, course=course, status=CourseEntitlement.Status.ACTIVE).update(status=CourseEntitlement.Status.REVOKED)


def create_order(learner, course):
    """A pending order whose price comes ONLY from the course in the database, converted to what Paystack can collect."""
    charge_amount, charge_currency, rate = fx.charge_quote(course.price, course.currency)
    return CourseOrder.objects.create(
        learner=learner, course=course, reference=new_reference(), amount=charge_amount, amount_minor=gateway.to_minor(charge_amount),
        currency=charge_currency, list_price=course.price, list_currency=course.currency, fx_rate=rate,
    )


@transaction.atomic
def refund_order(order):
    """Record that an order was refunded (the money itself is returned from the Paystack dashboard) and end the access it gave."""
    order = CourseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != CourseOrder.Status.SUCCESS:
        return order, False
    order.status = CourseOrder.Status.REFUNDED
    order.refunded_at = timezone.now()
    order.save(update_fields=["status", "refunded_at"])
    CourseEntitlement.objects.filter(order=order, status=CourseEntitlement.Status.ACTIVE).update(status=CourseEntitlement.Status.REVOKED)
    return order, True


def fulfil(reference, data):
    """Apply a VERIFIED Paystack answer to an order. Safe to call any number of times, from any number of places.

    Returns (order, outcome): "paid", "already_paid", "failed", "pending" or "unknown".
    """
    with transaction.atomic():
        order = CourseOrder.objects.select_for_update().filter(reference=reference).select_related("course", "learner").first()
        if order is None:
            return None, "unknown"
        if order.status in (CourseOrder.Status.SUCCESS, CourseOrder.Status.REFUNDED):
            return order, "already_paid"  # the first writer won; a refunded order is never re-activated by a late retry

        status = str(data.get("status", ""))[:40]
        order.gateway_status = status
        if status == "success":
            problem = gateway.mismatch_reason(order, data)
            if problem:
                # Money moved but not the amount (or currency) we asked for: never grant access automatically.
                order.status = CourseOrder.Status.FAILED
                order.failure_reason = problem
                order.save(update_fields=["status", "gateway_status", "failure_reason"])
                logger.error("Academy payment %s did not match its order (%s); access not granted", reference, problem)
                return order, "failed"
            order.status = CourseOrder.Status.SUCCESS
            order.paystack_transaction_id = str(data.get("id", ""))[:40]
            order.verified_at = timezone.now()
            order.failure_reason = ""
            order.save(update_fields=["status", "gateway_status", "paystack_transaction_id", "verified_at", "failure_reason"])
            grant_access(order.learner, order.course, source=CourseEntitlement.Source.PURCHASE, order=order)
            return order, "paid"
        if status in ("failed", "abandoned", "reversed"):
            order.status = CourseOrder.Status.FAILED
            order.failure_reason = status
            order.save(update_fields=["status", "gateway_status", "failure_reason"])
            return order, "failed"
        order.save(update_fields=["gateway_status"])  # ongoing, pending, queued ...: not decided yet
        return order, "pending"


def verify_and_fulfil(order, client=None):
    """Ask Paystack about `order` (server-to-server) and apply the answer."""
    client = client or get_client()
    return fulfil(order.reference, client.verify(order.reference))
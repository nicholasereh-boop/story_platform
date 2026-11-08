"""Paid courses: checkout, payment verification, the Paystack webhook, the learner's orders, and the staff tools for orders and
complimentary access. The browser never decides anything about money: the price is read from the database and every payment
is confirmed by asking Paystack from the server."""
import hashlib
import json
from datetime import datetime, time

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import service as audit
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsStaffUser
from apps.core.throttles import FlexibleScopedRateThrottle

from .errors import BadGateway, Conflict, ServiceUnavailable
from .models import AcademyPaymentEvent, Course, CourseEntitlement, CourseOrder
from .permissions import AcademyEnabled, IsActiveUser
from .services import entitlements, payments


def order_data(order):
    return {
        "id": order.pk, "reference": order.reference, "status": order.status, "amount": f"{order.amount:.2f}", "currency": order.currency,
        "list_price": f"{order.list_price:.2f}" if order.list_price is not None else None, "list_currency": order.list_currency,
        "created_at": order.created_at, "verified_at": order.verified_at, "refunded_at": order.refunded_at,
        "course": {"id": order.course_id, "slug": order.course.slug, "title": order.course.title, "access_type": order.course.access_type},
        "has_access": entitlements.has_access(order.learner, order.course) if order.status == CourseOrder.Status.SUCCESS else False,
    }


class CourseCheckoutView(APIView):
    """POST /academy/courses/<id>/checkout/. The PRICE IS READ FROM THE DATABASE; anything the browser sends about money is ignored."""

    permission_classes = [AcademyEnabled, IsActiveUser]
    parser_classes = [JSONParser]
    throttle_scope = "academy_checkout"

    def post(self, request, pk, **kwargs):
        course = get_object_or_404(Course, pk=pk, status=Course.Status.PUBLISHED)
        if not course.is_paid or course.price <= 0:
            raise Conflict("This course is free. Use Start learning instead.")
        if entitlements.has_access(request.user, course):
            raise Conflict("You already own this course. Find it under My learning.")
        try:
            client = payments.get_client()  # refuses (503) when no secret key is configured
        except payments.PaystackError as exc:
            raise (ServiceUnavailable if exc.status == 503 else BadGateway)(exc.message)
        try:
            order = payments.create_order(request.user, course)  # dollars -> what Paystack can collect
        except payments.RateUnavailable:
            raise ServiceUnavailable("Payments are not available right now. Please try again shortly.")
        callback = f"{settings.FRONTEND_URL}/academy/orders?reference={order.reference}"
        try:
            data = client.initialize(
                email=request.user.email, amount_minor=order.amount_minor, reference=order.reference, currency=order.currency,
                callback_url=callback, metadata={"academy_order_id": order.pk, "course_id": course.pk},
            )
        except payments.PaystackError as exc:
            order.status = CourseOrder.Status.FAILED
            order.failure_reason = "initialize_failed"
            order.save(update_fields=["status", "failure_reason"])
            raise (ServiceUnavailable if exc.status == 503 else BadGateway)(exc.message)
        url = str(data.get("authorization_url", ""))
        if not url.startswith("https://"):
            order.status = CourseOrder.Status.FAILED
            order.failure_reason = "bad_checkout_url"
            order.save(update_fields=["status", "failure_reason"])
            raise BadGateway()
        return Response({
            "reference": order.reference, "authorization_url": url, "amount": f"{order.amount:.2f}", "currency": order.currency,
            "list_price": f"{order.list_price:.2f}", "list_currency": order.list_currency,
        })


class VerifyPaymentView(APIView):
    """POST {reference}: the learner's browser came back from Paystack. The SERVER asks Paystack; the browser's claim is not used."""

    permission_classes = [AcademyEnabled, IsActiveUser]
    parser_classes = [JSONParser]
    throttle_scope = "academy_verify"

    def post(self, request, **kwargs):
        reference = str(request.data.get("reference", "")).strip()[:64]
        order = CourseOrder.objects.filter(reference=reference, learner=request.user).select_related("course", "learner").first()
        if order is None:
            raise NotFound()
        if order.status != CourseOrder.Status.SUCCESS:
            try:
                order, outcome = payments.verify_and_fulfil(order)
            except payments.PaystackError as exc:
                raise (ServiceUnavailable if exc.status == 503 else BadGateway)(exc.message)
            if outcome == "paid":
                audit.log(request, "academy.purchase", order, course=order.course.title, amount=str(order.amount), currency=order.currency, via="return")
        return Response(order_data(order))


class PaymentWebhookView(APIView):
    """Paystack calls this. Nothing in the body is believed until the signature is valid AND Paystack confirms it again."""

    authentication_classes = []
    permission_classes = [AcademyEnabled, AllowAny]
    parser_classes = []  # the body is read raw: the signature covers its exact bytes
    throttle_classes = [FlexibleScopedRateThrottle]
    throttle_scope = "academy_webhook"

    def post(self, request, **kwargs):
        raw = request.body
        if not payments.gateway.signature_is_valid(raw, request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")):
            return Response({"errors": {"detail": "Invalid signature."}, "message": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(raw.decode("utf-8"))
            event = str(payload.get("event", ""))[:60]
            reference = str((payload.get("data") or {}).get("reference", ""))[:64]
        except (ValueError, AttributeError, UnicodeDecodeError):
            return Response({"errors": {"detail": "Bad payload."}, "message": "Bad payload."}, status=status.HTTP_400_BAD_REQUEST)

        digest = hashlib.sha256(raw).hexdigest()
        record, created = AcademyPaymentEvent.objects.get_or_create(payload_hash=digest, defaults={"event": event, "reference": reference})
        if not created and record.processed_at:
            return Response({"received": True, "duplicate": True})

        outcome = "ignored"
        if event == "charge.success" and reference:
            order = CourseOrder.objects.filter(reference=reference).select_related("course", "learner").first()
            if order is None:
                outcome = "unknown_reference"  # not an Academy payment (it may belong to another part of the site)
            else:
                try:
                    verified = payments.get_client().verify(reference)  # never trust the webhook body itself
                except payments.PaystackError:
                    return Response({"errors": {"detail": "Try again later."}, "message": "Try again later."}, status=503)
                order, outcome = payments.fulfil(reference, verified)
                if outcome == "paid":
                    audit.log(request, "academy.purchase", order, actor=order.learner, course=order.course.title, amount=str(order.amount),
                              currency=order.currency, via="webhook")
        record.outcome = outcome
        record.processed_at = timezone.now()
        record.save(update_fields=["outcome", "processed_at"])
        return Response({"received": True})


class MyOrdersView(APIView):
    permission_classes = [AcademyEnabled, IsActiveUser]

    def get(self, request, **kwargs):
        orders = CourseOrder.objects.filter(learner=request.user).select_related("course", "learner").order_by("-created_at", "-id")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        return paginator.get_paginated_response([order_data(o) for o in page])


# ---------------------------------------------------------------- staff tools
class StaffView(APIView):
    permission_classes = [AcademyEnabled, IsStaffUser]
    parser_classes = [JSONParser]


def _learner_by_email(raw):
    from django.contrib.auth import get_user_model

    email = str(raw or "").strip().lower()
    if not email:
        raise serializers.ValidationError({"email": ["Enter the learner's email address."]})
    user = get_user_model().objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        raise serializers.ValidationError({"email": ["No active account has that email address."]})
    return user


class AdminOrderListView(StaffView):
    def get(self, request, **kwargs):
        qs = CourseOrder.objects.select_related("course", "learner").order_by("-created_at", "-id")
        status_ = request.query_params.get("status")
        if status_ in CourseOrder.Status.values:
            qs = qs.filter(status=status_)
        course = request.query_params.get("course")
        if course and course.isdigit():
            qs = qs.filter(course_id=int(course))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([{**order_data(o), "learner_email": o.learner.email} for o in page])


class AdminRefundView(StaffView):
    """POST: record a refund (the money is returned from the Paystack dashboard) and end the access that order gave."""

    def post(self, request, pk, **kwargs):
        order = get_object_or_404(CourseOrder.objects.select_related("course", "learner"), pk=pk)
        with transaction.atomic():
            order, changed = payments.refund_order(order)
            if not changed:
                raise Conflict("Only a paid order can be refunded.")
            audit.log(request, "academy.order_refund", order, course=order.course.title, amount=str(order.amount), currency=order.currency)
        return Response({**order_data(order), "learner_email": order.learner.email})


def _entitlement_data(e):
    return {"id": e.pk, "learner_email": e.learner.email, "source": e.source, "status": e.status, "starts_at": e.starts_at, "expires_at": e.expires_at,
            "note": e.note, "created_at": e.created_at}


class AdminCourseAccessView(StaffView):
    """GET the active and past entitlements of a course. POST {email, note?, expires_on?}: give complimentary access."""

    def get(self, request, pk, **kwargs):
        course = get_object_or_404(Course, pk=pk)
        items = CourseEntitlement.objects.filter(course=course).select_related("learner").order_by("-created_at", "-id")[:200]
        return Response([_entitlement_data(e) for e in items])

    def post(self, request, pk, **kwargs):
        course = get_object_or_404(Course, pk=pk)
        if not course.is_paid:
            raise Conflict("Free courses need no access grant.")
        learner = _learner_by_email(request.data.get("email"))
        note = str(request.data.get("note", ""))[:200]
        expires = None
        raw_date = request.data.get("expires_on")
        if raw_date:
            day = parse_date(str(raw_date))
            if day is None or day <= timezone.localdate():
                raise serializers.ValidationError({"expires_on": ["Choose a date in the future (YYYY-MM-DD), or leave it empty for lifetime access."]})
            expires = timezone.make_aware(datetime.combine(day, time.max))
        with transaction.atomic():
            entitlement, created = payments.grant_access(learner, course, source=CourseEntitlement.Source.GRANT, granted_by=request.user, note=note, expires_at=expires)
            if created:
                audit.log(request, "academy.access_grant", course, learner=learner.email, note=note, expires=str(expires.date()) if expires else "never")
        return Response(_entitlement_data(entitlement), status=201 if created else 200)

    def delete(self, request, pk, **kwargs):
        course = get_object_or_404(Course, pk=pk)
        learner = _learner_by_email(request.data.get("email") or request.query_params.get("email"))
        with transaction.atomic():
            revoked = payments.revoke_access(learner, course)
            if revoked:
                audit.log(request, "academy.access_revoke", course, learner=learner.email)
        return Response({"revoked": revoked})
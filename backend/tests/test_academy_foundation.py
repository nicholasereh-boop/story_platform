"""Phase 1: the Academy foundation: switch, config endpoint, and the database guarantees of the new tables."""
import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.academy.models import AcademyPaymentEvent, Course, CourseEntitlement, CourseOrder, Enrollment, LessonCommentGate, LessonProgress

from .academy_helpers import API, learner, learner2, make_course, make_lesson  # noqa: F401

pytestmark = pytest.mark.django_db


def test_the_config_endpoint_is_public_and_shows_nothing_private(settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_x"
    r = APIClient().get(API + "config/")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["enabled"] is True and data["currency"] == "USD" and data["payments_enabled"] is True
    assert "sk_test_x" not in r.content.decode()


def test_with_no_payment_key_the_config_says_payments_are_off(settings):
    settings.PAYSTACK_SECRET_KEY = ""
    assert APIClient().get(API + "config/").json()["data"]["payments_enabled"] is False


def test_switching_the_academy_off_answers_404_and_leaves_the_rest_of_the_site_alone(settings):
    settings.ACADEMY_ENABLED = False
    assert APIClient().get(API + "config/").status_code == 404
    assert APIClient().get("/api/v1/marketplace/config/").status_code == 200  # an existing feature is untouched


def test_a_paid_course_must_have_a_price():
    with pytest.raises(IntegrityError), transaction.atomic():
        Course.objects.create(title="x", slug="paid-no-price", access_type="paid", price=0)
    assert make_course("paid-ok", access_type="paid", price=10).pk


def test_a_lesson_threshold_must_be_between_10_and_100_percent():
    course = make_course()
    for bad in (5, 101):
        with pytest.raises(IntegrityError), transaction.atomic():
            make_lesson(course, 1, completion_threshold=bad)
    assert make_lesson(course, 2, completion_threshold=100).pk


def test_one_row_per_learner_and_lesson_or_course(learner):
    course = make_course()
    lesson = make_lesson(course, 1)
    for model, kwargs in [(Enrollment, {"course": course}), (LessonProgress, {"lesson": lesson}), (LessonCommentGate, {"lesson": lesson})]:
        model.objects.create(learner=learner, **kwargs)
        with pytest.raises(IntegrityError), transaction.atomic():
            model.objects.create(learner=learner, **kwargs)


def test_only_one_active_entitlement_per_learner_and_course_but_old_ones_may_be_revoked(learner):
    course = make_course("paid", access_type="paid")
    CourseEntitlement.objects.create(learner=learner, course=course, source="grant", status="revoked")
    CourseEntitlement.objects.create(learner=learner, course=course, source="grant")
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseEntitlement.objects.create(learner=learner, course=course, source="grant")


def test_order_references_and_webhook_deliveries_are_unique(learner):
    course = make_course("paid", access_type="paid")
    CourseOrder.objects.create(learner=learner, course=course, reference="rbac_1", amount=10, amount_minor=1000, currency="NGN")
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseOrder.objects.create(learner=learner, course=course, reference="rbac_1", amount=10, amount_minor=1000, currency="NGN")
    AcademyPaymentEvent.objects.create(payload_hash="a" * 64, event="charge.success")
    with pytest.raises(IntegrityError), transaction.atomic():
        AcademyPaymentEvent.objects.create(payload_hash="a" * 64, event="charge.success")


def test_the_migrations_are_complete_and_additive():
    call_command("makemigrations", "--check", "--dry-run")  # raises if a model change has no migration
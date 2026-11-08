"""Paystack: server-side price, server-side verification, signature checks, idempotency, protected paid downloads."""
import json

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.source_marketplace.models import PaymentEvent, SourceDownload, SourcePackage, SourcePurchase
from apps.source_marketplace.services import payments

from .marketplace_helpers import (  # noqa: F401
    MP, SECRET, client_for, new_project, paystack, private_dirs, publish, seller, buyer, other_seller, signed, upload,
)

pytestmark = pytest.mark.django_db
HOOK = MP + "payments/webhook/"


@pytest.fixture
def paid(paystack, seller):
    """A published project whose BACKEND package costs 5,000.50 USD (frontend is free)."""
    c = client_for(seller)
    p = new_project(c)
    upload(c, p["id"], kind="backend")
    upload(c, p["id"], kind="frontend")
    publish(p["id"], backend_price="5000.50")
    return p


def checkout(user, project, **body):
    return client_for(user).post(MP + f"projects/{project['id']}/checkout/", {"kind": "backend", **body}, format="json")


def webhook(body, *, secret=SECRET, signature=None):
    raw, sig = signed(body, secret)
    return APIClient().post(HOOK, raw, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=signature or sig)


def started(buyer, paid, paystack):
    r = checkout(buyer, paid)
    assert r.status_code == 200, r.content
    return r.json()["data"]["reference"]


def backend_package():
    return SourcePackage.objects.get(kind="backend")


# ------------------------------------------------------------------ checkout
def test_checkout_uses_the_database_price_and_ignores_what_the_browser_sends(paid, buyer, paystack):
    r = checkout(buyer, paid, amount=1, price="1", amount_minor=100, currency="USD")
    d = r.json()["data"]
    assert r.status_code == 200 and d["amount"] == "5000.50" and d["currency"] == "USD"
    assert d["authorization_url"].startswith("https://checkout.paystack.com/")
    sent = paystack.initialized[0]
    assert sent["amount_minor"] == 500050 and sent["currency"] == "USD" and sent["email"] == "buyer@example.com"
    p = SourcePurchase.objects.get()
    assert p.status == "pending" and p.amount_minor == 500050 and p.reference == d["reference"] and p.reference.startswith("rb_")
    assert sent["callback_url"].endswith(f"/marketplace/purchases?reference={p.reference}")


def test_every_checkout_gets_a_unique_reference(paid, buyer, paystack):
    assert started(buyer, paid, paystack) != started(buyer, paid, paystack)


def test_checkout_refuses_free_packages_own_projects_unpublished_and_anonymous(paid, buyer, seller, paystack):
    assert client_for(buyer).post(MP + f"projects/{paid['id']}/checkout/", {"kind": "frontend"}, format="json").status_code == 400
    assert checkout(seller, paid).status_code == 409
    assert APIClient().post(MP + f"projects/{paid['id']}/checkout/", {"kind": "backend"}, format="json").status_code in (401, 403)
    from apps.source_marketplace.models import SourceProject
    SourceProject.objects.filter(pk=paid["id"]).update(status="draft")
    assert checkout(buyer, paid).status_code == 404
    assert SourcePurchase.objects.count() == 0


def test_payments_not_configured_says_so_and_free_downloads_still_work(paid, buyer, settings, monkeypatch):
    settings.PAYSTACK_SECRET_KEY = ""
    monkeypatch.undo()  # use the REAL get_client, which refuses without a key
    assert checkout(buyer, paid).status_code == 503
    assert SourcePurchase.objects.count() == 0
    free = SourcePackage.objects.get(kind="frontend")
    assert client_for(buyer).get(MP + f"packages/{free.pk}/download/").status_code == 200


def test_if_paystack_is_down_the_purchase_is_marked_failed(paid, buyer, paystack):
    paystack.fail_initialize = True
    assert checkout(buyer, paid).status_code == 502
    assert SourcePurchase.objects.get().status == "failed"


# ------------------------------------------------------------------ verify (the buyer returns from Paystack)
def test_paid_access_is_locked_until_the_server_verifies(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    url = MP + f"packages/{backend_package().pk}/download/"
    assert client_for(buyer).get(url).status_code == 403  # started but not paid
    r = client_for(buyer).post(MP + "payments/verify/", {"reference": ref}, format="json")
    assert r.status_code == 200 and r.json()["data"]["status"] == "success" and r.json()["data"]["can_download"] is True
    assert paystack.verified == [ref]
    ok = client_for(buyer).get(url)
    assert ok.status_code == 200
    d = SourceDownload.objects.get()
    assert d.basis == "purchase" and d.purchase.reference == ref
    entry = AuditLog.objects.get(action="marketplace.purchase")
    assert entry.metadata["amount"] == "5000.50"


@pytest.mark.parametrize("override,reason", [
    ({"amount": 100}, "amount_mismatch"),
    ({"currency": "NGN"}, "currency_mismatch"),  # paid in a different currency than the one asked for
    ({"reference": "rb_someone_elses"}, "reference_mismatch"),
])
def test_a_payment_that_does_not_match_exactly_grants_nothing(paid, buyer, paystack, override, reason):
    ref = started(buyer, paid, paystack)
    paystack.result = override
    r = client_for(buyer).post(MP + "payments/verify/", {"reference": ref}, format="json")
    assert r.json()["data"]["status"] == "failed"
    assert SourcePurchase.objects.get().failure_reason == reason
    assert client_for(buyer).get(MP + f"packages/{backend_package().pk}/download/").status_code == 403
    assert not AuditLog.objects.filter(action="marketplace.purchase").exists()


@pytest.mark.parametrize("gateway,expected", [("failed", "failed"), ("abandoned", "failed"), ("ongoing", "pending"), ("pending", "pending")])
def test_failed_and_unfinished_payments(paid, buyer, paystack, gateway, expected):
    ref = started(buyer, paid, paystack)
    paystack.result = {"status": gateway}
    assert client_for(buyer).post(MP + "payments/verify/", {"reference": ref}, format="json").json()["data"]["status"] == expected
    assert client_for(buyer).get(MP + f"packages/{backend_package().pk}/download/").status_code == 403


def test_a_pending_purchase_can_still_succeed_later(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    paystack.result = {"status": "ongoing"}
    client_for(buyer).post(MP + "payments/verify/", {"reference": ref}, format="json")
    paystack.result = None
    assert client_for(buyer).post(MP + "payments/verify/", {"reference": ref}, format="json").json()["data"]["status"] == "success"


def test_verify_is_idempotent_and_cannot_be_used_on_someone_elses_purchase(paid, buyer, other_seller, paystack):
    ref = started(buyer, paid, paystack)
    c = client_for(buyer)
    c.post(MP + "payments/verify/", {"reference": ref}, format="json")
    c.post(MP + "payments/verify/", {"reference": ref}, format="json")
    assert SourcePurchase.objects.filter(status="success").count() == 1 and AuditLog.objects.filter(action="marketplace.purchase").count() == 1
    assert client_for(other_seller).post(MP + "payments/verify/", {"reference": ref}, format="json").status_code == 404
    assert client_for(buyer).post(MP + "payments/verify/", {"reference": "nope"}, format="json").status_code == 404


def test_buying_twice_is_refused_once_paid(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    client_for(buyer).post(MP + "payments/verify/", {"reference": ref}, format="json")
    assert checkout(buyer, paid).status_code == 409


def test_a_paystack_outage_during_verify_is_a_retryable_error_not_a_grant(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    paystack.fail_verify = True
    assert client_for(buyer).post(MP + "payments/verify/", {"reference": ref}, format="json").status_code == 502
    assert SourcePurchase.objects.get().status == "pending"


# ------------------------------------------------------------------ webhook
def event(ref, name="charge.success"):
    return {"event": name, "data": {"reference": ref, "status": "success"}}


def test_webhook_with_a_bad_or_missing_signature_is_rejected_and_changes_nothing(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    assert webhook(event(ref), signature="0" * 128).status_code == 401
    assert webhook(event(ref), secret="sk_test_attacker_guess").status_code == 401
    raw = json.dumps(event(ref)).encode()
    assert APIClient().post(HOOK, raw, content_type="application/json").status_code == 401
    assert SourcePurchase.objects.get().status == "pending" and PaymentEvent.objects.count() == 0 and paystack.verified == []


def test_a_signed_body_that_was_tampered_with_fails(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    raw, sig = signed(event(ref))
    tampered = raw.replace(ref.encode(), b"rb_other_reference")
    assert APIClient().post(HOOK, tampered, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig).status_code == 401


def test_valid_webhook_grants_access_after_the_server_re_verifies(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    r = webhook(event(ref))
    assert r.status_code == 200
    assert paystack.verified == [ref]  # the body was not believed on its own
    assert SourcePurchase.objects.get().status == "success"
    assert client_for(buyer).get(MP + f"packages/{backend_package().pk}/download/").status_code == 200


def test_webhook_for_a_payment_paystack_does_not_confirm_grants_nothing(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    paystack.result = {"status": "failed"}
    webhook(event(ref))
    assert SourcePurchase.objects.get().status == "failed"


def test_duplicate_and_replayed_webhooks_are_harmless(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    assert webhook(event(ref)).status_code == 200
    second = webhook(event(ref))
    assert second.status_code == 200 and second.json()["data"].get("duplicate") is True
    client_for(buyer).post(MP + "payments/verify/", {"reference": ref}, format="json")  # the browser races the webhook
    assert SourcePurchase.objects.filter(status="success").count() == 1
    assert AuditLog.objects.filter(action="marketplace.purchase").count() == 1 and PaymentEvent.objects.count() == 1


def test_unknown_references_and_other_events_are_acknowledged_and_ignored(paid, buyer, paystack):
    assert webhook(event("rb_does_not_exist")).status_code == 200
    assert webhook(event("rb_x", "transfer.success")).status_code == 200
    assert paystack.verified == [] and SourcePurchase.objects.count() == 0


def test_if_paystack_cannot_be_asked_the_webhook_asks_for_a_retry(paid, buyer, paystack):
    ref = started(buyer, paid, paystack)
    paystack.fail_verify = True
    assert webhook(event(ref)).status_code == 503
    assert PaymentEvent.objects.get().processed_at is None  # so the retry is processed, not skipped as a duplicate
    paystack.fail_verify = False
    assert webhook(event(ref)).status_code == 200 and SourcePurchase.objects.get().status == "success"


def test_webhook_refuses_everything_when_no_secret_is_configured(paid, buyer, paystack, settings):
    ref = started(buyer, paid, paystack)
    raw, sig = signed(event(ref))
    settings.PAYSTACK_SECRET_KEY = ""
    assert APIClient().post(HOOK, raw, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig).status_code == 401


# ------------------------------------------------------------------ units
def test_money_conversion_is_exact():
    from decimal import Decimal
    assert payments.to_minor(Decimal("5000.50")) == 500050 and payments.to_minor(Decimal("0.07")) == 7 and payments.to_minor(Decimal("19.99")) == 1999


def test_signature_helper_rules(private_dirs):
    raw, sig = signed({"a": 1})
    assert payments.signature_is_valid(raw, sig) and payments.signature_is_valid(raw, sig.upper())
    assert not payments.signature_is_valid(raw, "") and not payments.signature_is_valid(raw + b" ", sig)

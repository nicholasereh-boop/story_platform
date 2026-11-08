"""Prices are in US dollars, and backend source code is never free: a buyer must pay through Paystack first."""
import pytest
import requests
from rest_framework.test import APIClient

from apps.source_marketplace.models import SourceProject, SourcePurchase
from apps.source_marketplace.services import payments

from .marketplace_helpers import (  # noqa: F401
    MP, SECRET, FakePaystack, client_for, new_project, paystack, private_dirs, publish, seller, buyer, other_seller, upload,
)

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/marketplace/projects/"


# ------------------------------------------------------------------ dollars
def test_the_site_currency_is_us_dollars_by_default(settings):
    assert settings.MARKETPLACE_CURRENCY == "USD"


def test_the_config_endpoint_tells_the_pages_the_currency_and_the_backend_rule(settings):
    settings.PAYSTACK_SECRET_KEY = ""
    d = APIClient().get(MP + "config/").json()["data"]
    assert d == {"currency": "USD", "backend_requires_payment": True, "max_price": 10000, "payments_enabled": False}
    settings.PAYSTACK_SECRET_KEY = SECRET
    assert APIClient().get(MP + "config/").json()["data"]["payments_enabled"] is True


def test_a_dollar_price_goes_to_paystack_in_cents_in_usd(paystack, seller, buyer):
    c = client_for(seller)
    p = new_project(c, backend_price="49.00")
    upload(c, p["id"], kind="backend")
    publish(p["id"])
    r = client_for(buyer).post(MP + f"projects/{p['id']}/checkout/", {"kind": "backend"}, format="json")
    assert r.status_code == 200 and r.json()["data"]["amount"] == "49.00" and r.json()["data"]["currency"] == "USD"
    sent = paystack.initialized[0]
    assert sent["amount_minor"] == 4900 and sent["currency"] == "USD"
    purchase = SourcePurchase.objects.get()
    assert (purchase.amount_minor, purchase.currency) == (4900, "USD")


def test_a_project_priced_before_the_switch_keeps_the_currency_it_was_priced_in(paystack, seller, buyer):
    c = client_for(seller)
    p = new_project(c, backend_price="5000")
    upload(c, p["id"], kind="backend")
    publish(p["id"])
    SourceProject.objects.filter(pk=p["id"]).update(currency="NGN")  # created back when the site sold in naira
    client_for(buyer).post(MP + f"projects/{p['id']}/checkout/", {"kind": "backend"}, format="json")
    assert paystack.initialized[0]["currency"] == "NGN" and paystack.initialized[0]["amount_minor"] == 500000  # never silently re-read as dollars


def test_the_highest_price_is_enforced_in_dollars(seller):
    r = client_for(seller).post(MP + "projects/", {"title": "Big", "backend_price": "10001"}, format="json")
    assert r.status_code == 400 and "10,000 USD" in r.json()["errors"]["backend_price"][0]


# ------------------------------------------------------------------ backend code is always paid
def backend_project(client, **fields):
    p = new_project(client, rights_confirmed=True, **fields)
    assert upload(client, p["id"], kind="backend").status_code == 201
    return p


def test_a_backend_package_cannot_be_submitted_for_free(private_dirs, seller):
    c = client_for(seller)
    p = backend_project(c)  # backend price left at 0
    r = c.post(MP + f"projects/{p['id']}/submit/")
    assert r.status_code == 400 and "above 0" in r.json()["errors"]["backend_price"][0] and "USD" in r.json()["errors"]["backend_price"][0]
    assert SourceProject.objects.get(pk=p["id"]).status == "draft"
    assert c.patch(MP + f"projects/{p['id']}/", {"backend_price": "29"}, format="json").status_code == 200
    assert c.post(MP + f"projects/{p['id']}/submit/").json()["data"]["status"] == "pending"


def test_the_price_cannot_be_set_back_to_zero_while_a_backend_package_exists(private_dirs, seller):
    c = client_for(seller)
    p = backend_project(c, backend_price="29")
    r = c.patch(MP + f"projects/{p['id']}/", {"backend_price": "0"}, format="json")
    assert r.status_code == 400 and "backend_price" in r.json()["errors"]
    assert SourceProject.objects.get(pk=p["id"]).backend_price == 29


def test_a_free_frontend_is_still_fine_and_a_project_with_no_backend_may_have_backend_price_zero(private_dirs, seller):
    c = client_for(seller)
    p = new_project(c, rights_confirmed=True, frontend_price="0", backend_price="0")
    assert upload(c, p["id"], kind="frontend").status_code == 201
    assert c.post(MP + f"projects/{p['id']}/submit/").json()["data"]["status"] == "pending"


def test_staff_cannot_approve_a_project_whose_backend_is_unpriced(private_dirs, seller, staff):
    c = client_for(seller)
    p = backend_project(c)
    SourceProject.objects.filter(pk=p["id"]).update(status="pending")  # reached the queue some other way
    r = client_for(staff).post(ADMIN + f"{p['id']}/approve/")
    assert r.status_code == 409 and "above 0" in r.json()["message"]
    assert SourceProject.objects.get(pk=p["id"]).status == "pending"


def test_the_rule_can_be_switched_off(private_dirs, settings, seller):
    settings.MARKETPLACE_BACKEND_REQUIRES_PAYMENT = False
    c = client_for(seller)
    p = backend_project(c)
    assert c.post(MP + f"projects/{p['id']}/submit/").status_code == 200
    assert APIClient().get(MP + "config/").json()["data"]["backend_requires_payment"] is False


def test_an_unpaid_backend_cannot_be_downloaded_and_checkout_is_the_only_way_in(paystack, seller, buyer):
    c = client_for(seller)
    p = new_project(c, backend_price="49")
    upload(c, p["id"], kind="backend")
    publish(p["id"])
    package_id = [o for o in APIClient().get(MP + f"projects/{p['slug']}/").json()["data"]["offers"] if o["kind"] == "backend"][0]["package_id"]
    r = client_for(buyer).get(MP + f"packages/{package_id}/download/")
    assert r.status_code == 403 and "Buy" in r.json()["message"]
    assert APIClient().get(MP + f"packages/{package_id}/download/").status_code in (401, 403)
    ok = client_for(buyer).post(MP + f"projects/{p['id']}/checkout/", {"kind": "backend"}, format="json")
    assert ok.status_code == 200 and ok.json()["data"]["authorization_url"].startswith("https://checkout.paystack.com/")


# ------------------------------------------------------------------ USD must be enabled on the Paystack account
class Session:
    def __init__(self, status, body):
        self.status, self.body = status, body

    def request(self, *a, **kw):
        s, b = self.status, self.body

        class R:
            status_code = s
            def json(self_inner):
                return b
        return R()


def test_paystack_saying_the_currency_is_not_supported_becomes_a_clear_message(private_dirs):
    client = payments.PaystackClient(secret_key=SECRET, session=Session(400, {"status": False, "message": "Currency not supported by merchant"}))
    with pytest.raises(payments.PaystackError) as err:
        client.initialize(email="a@b.co", amount_minor=100, reference="r", currency="USD", callback_url="https://x.y/")
    assert err.value.status == 503 and "not enabled on the store's Paystack account" in err.value.message


def test_other_paystack_errors_stay_generic_and_never_echo_paystack_text(private_dirs):
    client = payments.PaystackClient(secret_key=SECRET, session=Session(400, {"status": False, "message": "Invalid key sk_live_abcdef"}))
    with pytest.raises(payments.PaystackError) as err:
        client.verify("r")
    assert err.value.status == 502 and "sk_live" not in err.value.message and "Invalid" not in err.value.message


def test_checkout_tells_the_buyer_when_dollars_are_not_enabled_and_records_nothing_as_paid(paystack, seller, buyer):
    c = client_for(seller)
    p = new_project(c, backend_price="49")
    upload(c, p["id"], kind="backend")
    publish(p["id"])

    def refuse(**kwargs):
        raise payments.PaystackError("Payments in this currency are not enabled on the store's Paystack account yet. Please contact the site owner.", 503)

    paystack.initialize = refuse
    r = client_for(buyer).post(MP + f"projects/{p['id']}/checkout/", {"kind": "backend"}, format="json")
    assert r.status_code == 503 and "not enabled" in r.json()["message"]
    assert SourcePurchase.objects.get().status == "failed"

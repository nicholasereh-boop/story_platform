"""Paystack: checkout, server-side verification, webhook signature and idempotent fulfilment.

Rules this module enforces (docs/extension road map/README.md, "Paystack payment requirements"):
  1. price and currency come from the database, never from the browser;
  2. every purchase gets its own unique reference;
  3. checkout is initialised by the SERVER with the secret key;
  4. a payment only counts after the SERVER asks Paystack and the status, reference, amount and currency all match;
  5. webhooks are checked against the HMAC-SHA512 signature before anything is read from them;
  6. fulfilment is idempotent: retries, duplicates and the verify-vs-webhook race cannot grant twice;
  7. access is granted only by `fulfil()`; the secret key lives only in server configuration.
"""
import hashlib
import hmac
import logging
import secrets
from decimal import ROUND_HALF_UP, Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import SourcePurchase

logger = logging.getLogger(__name__)


class PaystackError(Exception):
    """Something went wrong talking to Paystack. `message` is safe to show."""

    def __init__(self, message, status=502):
        super().__init__(message)
        self.message = message
        self.status = status


class PaymentsNotConfigured(PaystackError):
    def __init__(self):
        super().__init__("Payments are not available right now.", 503)


def to_minor(amount):
    """Major units -> kobo/cents, exactly (Decimal, no floats)."""
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def new_reference():
    return f"rb_{secrets.token_hex(16)}"


class PaystackClient:
    def __init__(self, secret_key=None, base_url=None, timeout=None, session=None):
        self.secret_key = secret_key if secret_key is not None else settings.PAYSTACK_SECRET_KEY
        self.base_url = (base_url or settings.PAYSTACK_API_BASE).rstrip("/")
        self.timeout = timeout or settings.PAYSTACK_TIMEOUT
        self.session = session or requests.Session()
        if not self.secret_key:
            raise PaymentsNotConfigured()

    def _call(self, method, path, **kwargs):
        headers = {"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/json"}
        try:
            response = self.session.request(method, f"{self.base_url}{path}", headers=headers, timeout=self.timeout, **kwargs)
        except requests.RequestException:
            raise PaystackError("We could not reach the payment provider. Please try again.")
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code >= 400 or not body.get("status"):
            said = str(body.get("message", ""))[:200]
            logger.warning("Paystack %s %s answered %s: %s", method, path.split("?")[0], response.status_code, said)
            if "currenc" in said.lower():  # e.g. "Currency not supported by merchant": USD is not switched on for this account
                raise PaystackError(
                    "Payments in this currency are not enabled on the store's Paystack account yet. Please contact the site owner.", 503)
            raise PaystackError("The payment provider could not process this request.")
        return body.get("data") or {}

    def initialize(self, *, email, amount_minor, reference, currency, callback_url, metadata=None):
        payload = {"email": email, "amount": int(amount_minor), "currency": currency, "reference": reference,
                   "callback_url": callback_url, "metadata": metadata or {}}
        try:
            return self._call("POST", "/transaction/initialize", json=payload)
        except PaystackError:
            logger.warning("Paystack initialize was sent currency=%s amount_minor=%s", currency, int(amount_minor))  # helps spot a wrong currency
            raise
    def verify(self, reference):
        return self._call("GET", f"/transaction/verify/{reference}")


def get_client():
    """The one place the client is built (tests replace this)."""
    return PaystackClient()


def signature_is_valid(raw_body, header_value):
    """HMAC-SHA512 of the exact request body, keyed with the secret key, compared in constant time."""
    secret = settings.PAYSTACK_SECRET_KEY
    if not secret or not header_value:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, str(header_value).strip().lower())


def mismatch_reason(purchase, data):
    """None when Paystack's answer confirms THIS purchase exactly, otherwise a short machine-readable reason."""
    if str(data.get("reference", "")) != purchase.reference:
        return "reference_mismatch"
    if int(data.get("amount") or -1) != int(purchase.amount_minor):
        return "amount_mismatch"
    if str(data.get("currency", "")).upper() != purchase.currency.upper():
        return "currency_mismatch"
    return None


def fulfil(reference, data):
    """Apply a VERIFIED Paystack answer to a purchase. Safe to call any number of times, from any number of places.

    Returns (purchase, outcome) where outcome is one of: "paid", "already_paid", "failed", "pending", "unknown".
    """
    with transaction.atomic():
        purchase = SourcePurchase.objects.select_for_update().filter(reference=reference).select_related("package__project").first()
        if purchase is None:
            return None, "unknown"
        if purchase.status == SourcePurchase.Status.SUCCESS:
            return purchase, "already_paid"  # the first writer won; nothing changes

        gateway = str(data.get("status", ""))[:40]
        purchase.gateway_status = gateway
        if gateway == "success":
            problem = mismatch_reason(purchase, data)
            if problem:
                # Money moved but not the amount (or currency) we asked for: never grant access automatically.
                purchase.status = SourcePurchase.Status.FAILED
                purchase.failure_reason = problem
                purchase.save(update_fields=["status", "gateway_status", "failure_reason"])
                logger.error("Paystack payment %s did not match its purchase (%s); access not granted", reference, problem)
                return purchase, "failed"
            purchase.status = SourcePurchase.Status.SUCCESS
            purchase.paystack_transaction_id = str(data.get("id", ""))[:40]
            purchase.verified_at = timezone.now()
            purchase.failure_reason = ""
            purchase.save(update_fields=["status", "gateway_status", "paystack_transaction_id", "verified_at", "failure_reason"])
            return purchase, "paid"
        if gateway in ("failed", "abandoned", "reversed"):
            purchase.status = SourcePurchase.Status.FAILED
            purchase.failure_reason = gateway
            purchase.save(update_fields=["status", "gateway_status", "failure_reason"])
            return purchase, "failed"
        purchase.save(update_fields=["gateway_status"])  # ongoing, pending, queued ...: not decided yet
        return purchase, "pending"


def verify_and_fulfil(purchase, client=None):
    """Ask Paystack about `purchase` (server-to-server) and apply the answer."""
    client = client or get_client()
    data = client.verify(purchase.reference)
    return fulfil(purchase.reference, data)

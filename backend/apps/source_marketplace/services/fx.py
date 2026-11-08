"""Prices are listed in US dollars; Paystack charges the equivalent in the currency the store's Paystack account can
collect (naira by default). The server decides the rate and the amount; the browser never sends either.

Rate order: a live rate (cached for an hour) when MARKETPLACE_FX_LIVE is on, otherwise / if that fails the fixed
MARKETPLACE_FX_RATE from the settings. With neither, checkout is refused rather than guessing a price.
"""
import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_SECONDS = 3600
MIN_RATE, MAX_RATE = Decimal("0.0001"), Decimal("1000000")  # anything outside this is a bad answer, not a price


class RateUnavailable(Exception):
    """No trustworthy exchange rate right now."""


def _sane(rate):
    return MIN_RATE < rate < MAX_RATE


def _live_rate(base, quote):
    key = f"marketplace:fx:{base}:{quote}"
    try:
        cached = cache.get(key)
        if cached:
            return Decimal(str(cached))
    except Exception:  # a broken cache must never stop a purchase
        pass
    try:
        response = requests.get(f"{settings.MARKETPLACE_FX_URL.rstrip('/')}/{base}", timeout=settings.MARKETPLACE_FX_TIMEOUT)
        body = response.json()
        if response.status_code != 200 or body.get("result", "success") != "success":
            return None
        rate = Decimal(str(body["rates"][quote]))
    except (requests.RequestException, ValueError, KeyError, TypeError, InvalidOperation):
        logger.warning("Live exchange rate %s->%s could not be read; using the fixed rate", base, quote)
        return None
    if not _sane(rate):
        return None
    try:
        cache.set(key, str(rate), CACHE_SECONDS)
    except Exception:
        pass
    return rate


def _fixed_rate():
    raw = str(getattr(settings, "MARKETPLACE_FX_RATE", "") or "").strip()
    if not raw:
        return None
    try:
        rate = Decimal(raw)
    except InvalidOperation:
        return None
    return rate if _sane(rate) else None


def get_rate(base, quote):
    if base == quote:
        return Decimal(1)
    rate = _live_rate(base, quote) if getattr(settings, "MARKETPLACE_FX_LIVE", True) else None
    rate = rate or _fixed_rate()
    if rate is None:
        raise RateUnavailable(f"No exchange rate for {base}->{quote}")
    return rate


def charge_quote(price, listing_currency):
    """(charge_amount, charge_currency, rate): what Paystack is asked to collect for a package listed at `price`."""
    listing = str(listing_currency).upper()
    charge = str(getattr(settings, "MARKETPLACE_CHARGE_CURRENCY", "") or listing).upper()
    rate = get_rate(listing, charge)
    amount = (Decimal(price) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise RateUnavailable("The converted amount is not positive")
    return amount, charge, rate
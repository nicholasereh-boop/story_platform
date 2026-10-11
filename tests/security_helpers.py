"""Helpers for the Phase 10 tests: two-step verification enrolment and a controllable clock for TOTP."""
import time
import types

from apps.accounts import mfa, totp

from .conftest import PASSWORD


def enrol(user):
    """Give `user` a confirmed authenticator device. Returns (secret, recovery_codes)."""
    secret = mfa.start_setup(user)
    codes = mfa.confirm_setup(user, totp.totp_now(secret))
    assert codes, "enrolment failed"
    return secret, codes


def fake_clock(monkeypatch, at):
    """Pin the clock TOTP uses (only inside apps.accounts.totp). Returns a function that moves it."""
    clock = {"now": float(at)}
    monkeypatch.setattr(totp, "time", types.SimpleNamespace(time=lambda: clock["now"]))
    return clock


def code_at(secret, at):
    return totp.totp_now(secret, at=at)


def login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")


def verify(client, code):
    return client.post("/api/v1/auth/mfa/verify/", {"code": code}, format="json")


def now():
    return time.time()

"""Two-step verification (TOTP) for staff: RFC vectors, window, replay, recovery codes, permission-layer enforcement."""
import base64

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import mfa, totp
from apps.accounts.models import MFADevice, MFARecoveryCode
from apps.audit.models import AuditLog

from .conftest import PASSWORD
from .security_helpers import enrol, fake_clock, login, now, verify

API = "/api/v1/"
PING = API + "admin/ping/"
T0 = 1_800_000_000  # a fixed moment: step boundaries are easy to reason about (T0 // 30)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------- RFC 6238 (SHA-1) test vectors, 8 digits
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode().rstrip("=")


@pytest.mark.parametrize(
    "at, expected",
    [(59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"), (1234567890, "89005924"), (2000000000, "69279037"), (20000000000, "65353130")],
)
def test_rfc_6238_vectors(at, expected):
    assert totp.totp_now(RFC_SECRET, at=at, digits=8) == expected


def test_default_codes_have_six_digits_and_a_30_second_step():
    code = totp.totp_now(RFC_SECRET, at=59)
    assert len(code) == 6 and code == totp.totp_now(RFC_SECRET, at=30) == totp.totp_now(RFC_SECRET, at=59.9)
    assert code != totp.totp_now(RFC_SECRET, at=60)


def test_one_step_of_clock_drift_is_accepted_but_not_two():
    secret = totp.generate_secret()
    for drift, ok in ((-30, True), (0, True), (30, True), (-60, False), (60, False), (300, False)):
        step = totp.matching_step(secret, totp.totp_now(secret, at=T0 + drift), at=T0)
        assert (step is not None) is ok, drift


def test_garbage_codes_never_match():
    secret = totp.generate_secret()
    for bad in ("", "abc123", "12345", "1234567", None, "١٢٣٤٥٦", "      "):
        assert totp.matching_step(secret, bad, at=T0) is None


def test_secret_is_encrypted_at_rest(staff):
    secret, _ = enrol(staff)
    device = MFADevice.objects.get(user=staff)
    assert secret not in device.secret_encrypted and device.confirmed_at is not None
    assert totp.decrypt_secret(mfa._master(), device.secret_encrypted) == secret


# ---------------------------------------------------------------- setup / confirm
def test_setup_and_confirm_flow(client, staff):
    login(client, staff.email)
    r = client.post(API + "auth/mfa/setup/")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["otpauth_uri"].startswith("otpauth://totp/") and f"secret={data['secret']}" in data["otpauth_uri"]
    assert client.get(API + "auth/mfa/status/").json()["data"]["enabled"] is False
    assert client.post(API + "auth/mfa/confirm/", {"code": "000000"}, format="json").status_code == 400
    ok = client.post(API + "auth/mfa/confirm/", {"code": totp.totp_now(data["secret"])}, format="json")
    assert ok.status_code == 200
    codes = ok.json()["data"]["recovery_codes"]
    assert len(codes) == 10 and len(set(codes)) == 10
    status = client.get(API + "auth/mfa/status/").json()["data"]
    assert status["enabled"] is True and status["verified"] is True and status["recovery_codes_left"] == 10
    assert "secret" not in status and "recovery_codes" not in status
    assert AuditLog.objects.filter(action="mfa.enabled", actor=staff).count() == 1


def test_recovery_codes_are_stored_hashed(staff):
    _, codes = enrol(staff)
    stored = set(MFARecoveryCode.objects.filter(user=staff).values_list("code_hash", flat=True))
    assert len(stored) == 10 and not stored & set(codes)


def test_only_staff_can_use_mfa_endpoints(client, user):
    login(client, user.email)
    assert client.post(API + "auth/mfa/setup/").status_code == 403
    assert client.get(API + "auth/mfa/status/").status_code == 403
    assert APIClient().post(API + "auth/mfa/setup/").status_code in (401, 403)


def test_setup_is_refused_when_already_on(client, staff):
    enrol(staff)
    login(client, staff.email)
    assert client.post(API + "auth/mfa/setup/").status_code == 400


# ---------------------------------------------------------------- enforcement in the permission layer
def test_staff_without_a_device_are_not_asked_by_default(staff_client):
    assert staff_client.get(PING).status_code == 200


def test_login_then_verify_unlocks_the_admin(client, staff, monkeypatch):
    secret, _ = enrol(staff)
    clock = fake_clock(monkeypatch, T0)
    me = login(client, staff.email).json()["data"]
    assert me["mfa"] == {"enabled": True, "verified": False, "required": False}
    blocked = client.get(PING)
    assert blocked.status_code == 403 and blocked.json()["errors"]["code"] == "mfa_required"
    clock["now"] = T0 + 30  # a later step than the one used during enrolment (replay protection)
    ok = verify(client, totp.totp_now(secret, at=T0 + 30))
    assert ok.status_code == 200 and ok.json()["data"]["verified"] is True
    assert client.get(PING).status_code == 200
    assert client.get(API + "auth/me/").json()["data"]["mfa"]["verified"] is True


def test_a_session_that_skipped_verification_is_blocked(client, staff):
    """Google login and a stolen session cookie create a session without ever calling the MFA endpoints."""
    enrol(staff)
    client.force_login(staff)  # a plain Django login, like allauth does after Google
    r = client.get(PING)
    assert r.status_code == 403 and r.json()["errors"]["code"] == "mfa_required"
    assert client.get(API + "admin/stories/").status_code == 403
    assert client.get(API + "admin/users/").status_code == 403


def test_the_flag_belongs_to_one_user(client, staff, superuser, monkeypatch):
    secret, _ = enrol(staff)
    enrol(superuser)
    fake_clock(monkeypatch, T0 + 30)
    client.force_login(staff)
    verify(client, totp.totp_now(secret, at=T0 + 30))
    session = client.session
    session["_auth_user_id"] = str(superuser.pk)  # swap the account under a verified session
    session.save()
    assert client.get(PING).status_code == 403


def test_required_mode_sends_staff_without_a_device_to_setup(staff_client, settings):
    settings.STAFF_MFA_REQUIRED = True
    r = staff_client.get(PING)
    assert r.status_code == 403 and r.json()["errors"]["code"] == "mfa_setup_required"


def test_required_mode_does_not_affect_readers(client, user, settings):
    settings.STAFF_MFA_REQUIRED = True
    login(client, user.email)
    assert client.get(API + "auth/me/").status_code == 200
    assert client.get(PING).status_code == 403  # a plain permission denial, not an MFA code
    assert "code" not in client.get(PING).json()["errors"] or client.get(PING).json()["errors"].get("code") not in ("mfa_required", "mfa_setup_required")


def test_the_superuser_permission_enforces_it_too(client, superuser):
    enrol(superuser)
    client.force_login(superuser)
    r = client.patch(API + f"admin/users/{superuser.pk}/", {"is_active": True}, format="json")
    assert r.status_code == 403 and r.json()["errors"]["code"] == "mfa_required"


def test_setup_then_verify_works_in_required_mode(client, staff, settings):
    settings.STAFF_MFA_REQUIRED = True
    login(client, staff.email)
    secret = client.post(API + "auth/mfa/setup/").json()["data"]["secret"]
    assert client.get(PING).status_code == 403
    client.post(API + "auth/mfa/confirm/", {"code": totp.totp_now(secret)}, format="json")
    assert client.get(PING).status_code == 200  # confirming proves possession: this session is verified


# ---------------------------------------------------------------- replay, recovery, failures
def test_a_code_works_only_once(client, staff, monkeypatch):
    secret, _ = enrol(staff)
    fake_clock(monkeypatch, T0 + 30)
    login(client, staff.email)
    code = totp.totp_now(secret, at=T0 + 30)
    assert verify(client, code).status_code == 200
    assert verify(client, code).status_code == 400
    assert totp.totp_now(secret, at=T0 + 30) == code  # still the "right" code for this step: only the replay rule refuses it


def test_the_enrolment_code_cannot_be_replayed_to_verify(client, staff, monkeypatch):
    clock = fake_clock(monkeypatch, T0)
    secret = mfa.start_setup(staff)
    mfa.confirm_setup(staff, totp.totp_now(secret, at=T0))
    login(client, staff.email)
    assert verify(client, totp.totp_now(secret, at=T0)).status_code == 400


def test_an_older_step_cannot_be_used_after_a_newer_one(client, staff, monkeypatch):
    secret, _ = enrol(staff)
    fake_clock(monkeypatch, T0 + 30)
    login(client, staff.email)
    assert verify(client, totp.totp_now(secret, at=T0 + 30)).status_code == 200
    assert verify(client, totp.totp_now(secret, at=T0)).status_code == 400  # earlier step, still inside the window


def test_wrong_code_is_rejected_and_audited(client, staff):
    enrol(staff)
    login(client, staff.email)
    r = verify(client, "000000")
    assert r.status_code == 400 and client.get(PING).status_code == 403
    assert AuditLog.objects.filter(action="mfa.verify_failed", actor=staff).exists()


def test_recovery_codes_work_once(client, staff):
    _, codes = enrol(staff)
    login(client, staff.email)
    r = client.post(API + "auth/mfa/verify/", {"recovery_code": codes[0]}, format="json")
    assert r.status_code == 200 and r.json()["data"]["recovery_codes_left"] == 9
    assert client.get(PING).status_code == 200
    assert AuditLog.objects.filter(action="mfa.recovery_used", actor=staff).count() == 1
    other = APIClient()
    login(other, staff.email)
    assert other.post(API + "auth/mfa/verify/", {"recovery_code": codes[0]}, format="json").status_code == 400
    assert other.post(API + "auth/mfa/verify/", {"code": codes[1].upper()}, format="json").status_code == 200  # case-insensitive, via "code" too


def test_verify_requires_a_device(client, staff):
    login(client, staff.email)
    assert verify(client, "123456").status_code == 400


def test_mfa_attempts_are_rate_limited(client, staff):
    enrol(staff)
    login(client, staff.email)
    codes = [verify(client, "000000").status_code for _ in range(12)]
    assert codes[:10] == [400] * 10 and codes[10] == 429


# ---------------------------------------------------------------- sensitive actions need a fresh code
def test_disabling_needs_password_and_a_fresh_code(client, staff, monkeypatch):
    secret, _ = enrol(staff)
    clock = fake_clock(monkeypatch, T0 + 30)
    login(client, staff.email)
    verify(client, totp.totp_now(secret, at=T0 + 30))
    url = API + "auth/mfa/disable/"
    assert client.post(url, {"password": "wrong", "code": totp.totp_now(secret, at=T0 + 60)}, format="json").status_code == 400
    clock["now"] = T0 + 60
    assert client.post(url, {"password": PASSWORD, "code": "000000"}, format="json").status_code == 400
    assert client.post(url, {"password": PASSWORD}, format="json").status_code == 400
    assert mfa.is_enabled(staff)
    used = totp.totp_now(secret, at=T0 + 60)
    clock["now"] = T0 + 90  # verify's code (step T0+30) is spent; use the next one
    assert client.post(url, {"password": PASSWORD, "code": totp.totp_now(secret, at=T0 + 90)}, format="json").status_code == 200
    assert not mfa.is_enabled(staff) and not MFARecoveryCode.objects.filter(user=staff).exists()
    assert AuditLog.objects.filter(action="mfa.disabled", actor=staff).count() == 1
    assert used  # (the unused step-60 code is deliberately skipped: only a later step than the last accepted one works)


def test_the_code_used_to_log_in_cannot_also_disable_mfa(client, staff, monkeypatch):
    secret, _ = enrol(staff)
    fake_clock(monkeypatch, T0 + 30)
    login(client, staff.email)
    code = totp.totp_now(secret, at=T0 + 30)
    verify(client, code)
    assert client.post(API + "auth/mfa/disable/", {"password": PASSWORD, "code": code}, format="json").status_code == 400


def test_new_recovery_codes_need_a_fresh_code(client, staff, monkeypatch):
    secret, old = enrol(staff)
    fake_clock(monkeypatch, T0 + 30)
    login(client, staff.email)
    r = client.post(API + "auth/mfa/recovery-codes/", {"password": PASSWORD, "code": "000000"}, format="json")
    assert r.status_code == 400
    ok = client.post(API + "auth/mfa/recovery-codes/", {"password": PASSWORD, "code": totp.totp_now(secret, at=T0 + 30)}, format="json")
    assert ok.status_code == 200
    fresh = ok.json()["data"]["recovery_codes"]
    assert len(fresh) == 10 and not set(fresh) & set(old)
    assert not mfa.check_recovery_code(staff, old[0]) and mfa.check_recovery_code(staff, fresh[0])
    assert AuditLog.objects.filter(action="mfa.recovery_regenerated").count() == 1


def test_changing_the_password_needs_a_fresh_code(client, staff, monkeypatch):
    secret, _ = enrol(staff)
    fake_clock(monkeypatch, T0 + 30)
    login(client, staff.email)
    body = {"current_password": PASSWORD, "new_password": "Brand-new-passphrase-42"}
    assert client.post(API + "auth/password/change/", body, format="json").status_code == 400
    assert client.post(API + "auth/password/change/", {**body, "code": totp.totp_now(secret, at=T0 + 30)}, format="json").status_code == 200


def test_staff_login_audit_for_google_style_logins(client, staff):
    client.force_login(staff)
    assert AuditLog.objects.filter(action="auth.staff_login", actor=staff).count() == 1

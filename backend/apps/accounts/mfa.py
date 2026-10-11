"""Two-step verification (TOTP) for staff: setup, verification, recovery codes and the enforcement rule.

How it fits together
  - setup()           starts enrolment: a new secret is stored (encrypted) in an UNCONFIRMED device. MFA is not on yet.
  - confirm()         the user proves they can produce a code; the device becomes confirmed and recovery codes are issued.
  - verify()          after logging in, a code (or a recovery code) marks THIS SESSION as verified.
  - enforcement_problem()  is called by the permission classes (apps/core/permissions.py) on every staff/admin request, so
                      Google login, a stolen session cookie or any other path into a session still meets the same check.

A code works once: the last accepted time step is stored and only later steps are accepted. The update is a single
conditional UPDATE, so two simultaneous requests with the same code cannot both succeed.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from . import totp
from .models import MFADevice, MFARecoveryCode

SESSION_FLAG = "mfa_verified"  # value = the user's id, so the flag cannot carry over to another account

MESSAGES = {
    "mfa_required": "Enter your two-step verification code to continue.",
    "mfa_setup_required": "Staff accounts must set up two-step verification before using the admin.",
}


def _master():
    return settings.MFA_ENCRYPTION_KEY or settings.SECRET_KEY


# ---------------------------------------------------------------- state
def confirmed_device(user):
    return MFADevice.objects.filter(user=user, confirmed_at__isnull=False).first()


def is_enabled(user):
    return MFADevice.objects.filter(user=user, confirmed_at__isnull=False).exists()


def session_verified(request, user):
    session = getattr(request, "session", None)
    return bool(session is not None and session.get(SESSION_FLAG) == user.pk)


def mark_verified(request, user):
    """Remember in the session that this browser passed the check. The session id is rotated (privilege change)."""
    from . import sessions

    raw = getattr(request, "_request", request)
    old_key = raw.session.session_key
    raw.session[SESSION_FLAG] = user.pk
    raw.session.cycle_key()
    sessions.after_key_rotation(raw, user, old_key)


def clear_verified(request):
    raw = getattr(request, "_request", request)
    session = getattr(raw, "session", None)
    if session is not None:
        session.pop(SESSION_FLAG, None)


def enforcement_problem(request, user):
    """None when the request may go on, else "mfa_required" or "mfa_setup_required".

    Applies to staff and superusers only. Looked up once per request (cached on the underlying Django request).
    """
    if not (user.is_staff or user.is_superuser):
        return None
    raw = getattr(request, "_request", request)
    if session_verified(raw, user):
        return None  # already proven in this session: no database lookup needed
    enrolled = getattr(raw, "_mfa_enrolled", None)
    if enrolled is None:
        enrolled = is_enabled(user)
        raw._mfa_enrolled = enrolled
    if enrolled:
        return None if session_verified(raw, user) else "mfa_required"
    if settings.STAFF_MFA_REQUIRED:
        return "mfa_setup_required"
    return None


def summary(request, user):
    """What the frontend needs to decide between "show the admin", "ask for a code" and "send to setup"."""
    if request is None or not (user.is_staff or user.is_superuser):
        return None
    enabled = is_enabled(user)
    return {
        "enabled": enabled,
        "verified": session_verified(request, user) if enabled else False,
        "required": bool(settings.STAFF_MFA_REQUIRED),
    }


# ---------------------------------------------------------------- enrolment
def start_setup(user):
    """Create (or replace an unconfirmed) device. Returns the plain secret, which is shown to the user once."""
    secret = totp.generate_secret()
    MFADevice.objects.update_or_create(
        user=user,
        confirmed_at__isnull=True,
        defaults={"secret_encrypted": totp.encrypt_secret(_master(), secret), "last_used_step": 0},
    )
    return secret


def _secret_of(device):
    try:
        return totp.decrypt_secret(_master(), device.secret_encrypted)
    except ValueError:
        return None  # key changed or data damaged: no code can match


def provisioning_uri(user, secret):
    return totp.provisioning_uri(secret, user.email, settings.MFA_ISSUER)


def confirm_setup(user, code):
    """Finish enrolment with a first valid code. Returns the ten recovery codes, or None when the code is wrong."""
    device = MFADevice.objects.filter(user=user, confirmed_at__isnull=True).first()
    secret = _secret_of(device) if device else None
    step = totp.matching_step(secret, code) if secret else None
    if step is None:
        return None
    done = MFADevice.objects.filter(pk=device.pk, confirmed_at__isnull=True).update(confirmed_at=timezone.now(), last_used_step=step)
    if not done:
        return None
    return issue_recovery_codes(user)


def issue_recovery_codes(user):
    """Replace all recovery codes with ten new ones. The plain codes are returned and never stored."""
    MFARecoveryCode.objects.filter(user=user).delete()
    codes = [totp.new_recovery_code() for _ in range(10)]
    MFARecoveryCode.objects.bulk_create(
        [MFARecoveryCode(user=user, code_hash=totp.hash_recovery_code(_master(), code)) for code in codes]
    )
    return codes


def recovery_codes_left(user):
    return MFARecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


# ---------------------------------------------------------------- checking codes
def check_totp(user, code):
    """True if `code` is valid and has not been used before. Marks its step as used."""
    device = confirmed_device(user)
    secret = _secret_of(device) if device else None
    step = totp.matching_step(secret, code) if secret else None
    if step is None:
        return False
    # One conditional UPDATE decides: only a step later than the last accepted one wins.
    return MFADevice.objects.filter(pk=device.pk, last_used_step__lt=step).update(last_used_step=step) == 1


def check_recovery_code(user, raw):
    code = totp.normalise_recovery_code(raw)
    if not code:
        return False
    digest = totp.hash_recovery_code(_master(), code)
    return MFARecoveryCode.objects.filter(user=user, code_hash=digest, used_at__isnull=True).update(used_at=timezone.now()) == 1


def check_any(user, payload):
    """Accepts {"code": "123456"}, {"code": "<recovery code>"} or {"recovery_code": "..."}.

    Returns "totp", "recovery" or None.
    """
    code = payload.get("code")
    recovery = payload.get("recovery_code")
    if code and totp.looks_like_totp(code):
        return "totp" if check_totp(user, code) else None
    candidate = recovery or code
    if candidate and check_recovery_code(user, candidate):
        return "recovery"
    return None


def require_fresh_code(user, payload):
    """For sensitive actions (turn MFA off, new recovery codes, change password): users with MFA must supply a code
    that has not been used before. Returns the kind used ("totp" / "recovery") or None when MFA is not on."""
    if not is_enabled(user):
        return None
    kind = check_any(user, payload)
    if kind is None:
        raise serializers.ValidationError(
            {"code": ["Enter a current two-step verification code (a code can only be used once)."], "detail": ["A valid two-step verification code is required."]}
        )
    return kind


def disable(user):
    MFADevice.objects.filter(user=user).delete()
    MFARecoveryCode.objects.filter(user=user).delete()

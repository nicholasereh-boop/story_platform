"""Browser sessions: a small registry (so they can be listed and revoked), idle timeout and revocation.

Django keeps sessions in the django_session table without saying whose they are. UserSession adds that, plus a coarse
device label. No IP address and no user-agent string is stored.
"""
import hashlib

from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.utils import timezone

from .models import UserSession

ACTIVITY_KEY = "_last_activity"  # unix time of the last request, kept in the session itself
TOUCH_EVERY_SECONDS = 60  # activity is written at most once a minute (idle checks do not need more)

_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
_SYSTEMS = (
    ("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
    ("Windows", "Windows"), ("Mac OS X", "macOS"), ("Linux", "Linux"),
)


def device_label(user_agent):
    """"Firefox on Linux": only the browser and system family are kept, never the full user-agent text."""
    agent = user_agent or ""
    browser = next((name for token, name in _BROWSERS if token in agent), "Unknown browser")
    system = next((name for token, name in _SYSTEMS if token in agent), "unknown system")
    return f"{browser} on {system}"


def public_id(session_key):
    """Opaque id shown to the client in place of the real session key (which is a secret)."""
    return hashlib.sha256(f"session|{session_key}".encode()).hexdigest()[:16]


def register(request, user):
    """Make sure the current session has a registry row. Called on login; safe to call again."""
    session = getattr(request, "session", None)
    if session is None:
        return None
    if not session.session_key:
        session.save()  # a fresh session has no key until it is stored
    label = device_label(getattr(request, "META", {}).get("HTTP_USER_AGENT", ""))
    row, _ = UserSession.objects.update_or_create(
        session_key=session.session_key, defaults={"user": user, "device": label, "last_seen_at": timezone.now()}
    )
    return row


def after_key_rotation(request, user, old_key):
    """The session id changed (MFA step-up, password change): carry the registry row over to the new id."""
    session = getattr(request, "session", None)
    if session is None or not session.session_key:
        return
    UserSession.objects.filter(session_key=old_key or "").exclude(session_key=session.session_key).delete()
    register(request, user)


def touch(request, user):
    """Refresh last-seen. A session without a registry row (for example one created before Phase 10) gets one."""
    updated = UserSession.objects.filter(session_key=request.session.session_key, user=user).update(last_seen_at=timezone.now())
    if not updated:
        register(request, user)


def listing(user, current_key):
    """The user's live sessions, newest activity first, as plain dicts. Dead registry rows are cleaned up."""
    rows = list(UserSession.objects.filter(user=user))
    alive = set(
        Session.objects.filter(session_key__in=[r.session_key for r in rows], expire_date__gt=timezone.now()).values_list(
            "session_key", flat=True
        )
    )
    dead = [r.pk for r in rows if r.session_key not in alive]
    if dead:
        UserSession.objects.filter(pk__in=dead).delete()
    return [
        {
            "id": public_id(r.session_key),
            "device": r.device or "Unknown device",
            "created_at": r.created_at,
            "last_seen_at": r.last_seen_at,
            "current": r.session_key == current_key,
        }
        for r in rows
        if r.session_key in alive
    ]


def revoke_all(user, except_key=None):
    """End every session of `user` (optionally keeping one). Returns how many were ended.

    Sessions are found through the registry AND by scanning unexpired Django sessions for this user, so sessions
    created before the registry existed (or never registered) are ended too.
    """
    keys = set(UserSession.objects.filter(user=user).values_list("session_key", flat=True))
    wanted = str(user.pk)
    for session in Session.objects.filter(expire_date__gt=timezone.now()).exclude(session_key__in=keys).iterator():
        try:
            if str(session.get_decoded().get(SESSION_KEY)) == wanted:
                keys.add(session.session_key)
        except Exception:  # an undecodable session is not ours to worry about
            continue
    if except_key:
        keys.discard(except_key)
    Session.objects.filter(session_key__in=keys).delete()
    UserSession.objects.filter(user=user).exclude(session_key=except_key or "").delete()
    return len(keys)

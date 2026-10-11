"""audit.log(): the one way to record an audit entry.

    from apps.audit import service as audit
    audit.log(request, "story.publish", story, title=story.title, status_from="draft", status_to="published")

Rules this helper enforces:
  - It never breaks the action it records. Any failure is logged and swallowed, and the write runs inside its own
    savepoint, so a database error cannot poison the caller's transaction.
  - Call it AFTER the change succeeded and inside the same `transaction.atomic()` block as the change: if that block
    rolls back, the entry rolls back with it (no entry for an action that did not happen).
  - Metadata is sanitised: keys that look sensitive are dropped, long strings are cut, everything must be JSON.
  - The client IP is stored only as a keyed hash.
"""
import hashlib
import hmac
import logging
from datetime import date, datetime

from django.conf import settings
from django.db import transaction
from rest_framework.throttling import BaseThrottle

from apps.core.text import sanitize_external_text

from .actions import ACTIONS
from .models import AuditLog

logger = logging.getLogger(__name__)

# A metadata KEY containing one of these fragments is dropped (stories' text is "content", comments' is "body", ...).
SENSITIVE_KEY_PARTS = (
    "password", "passwd", "token", "secret", "hash", "session", "cookie", "authorization",
    "recovery", "code", "body", "content", "text", "otp",
)
MAX_STRING = 200
MAX_ITEMS = 50
MAX_DEPTH = 3
SYSTEM_LABEL = "system"
TYPE_NAMES = {"mediaasset": "media"}


def _clean_value(value, depth=0):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        if depth >= MAX_DEPTH:
            return "..."
        return clean_metadata(value, depth + 1)
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=str) if isinstance(value, (set, frozenset)) else list(value)
        if depth >= MAX_DEPTH:
            return "..."
        return [_clean_value(item, depth + 1) for item in items[:MAX_ITEMS]]
    return str(value)[:MAX_STRING]


def clean_metadata(metadata, depth=0):
    """A JSON-safe copy of `metadata` without sensitive-looking keys."""
    cleaned = {}
    for key, value in (metadata or {}).items():
        name = str(key)
        lowered = name.lower()
        if any(part in lowered for part in SENSITIVE_KEY_PARTS):
            continue
        cleaned[name[:60]] = _clean_value(value, depth)
    return cleaned


def hash_ip(ip):
    """Keyed HMAC of an IP address (hex). Empty input gives an empty string."""
    if not ip:
        return ""
    key = (getattr(settings, "AUDIT_HASH_SECRET", "") or settings.SECRET_KEY) + "|audit-ip"
    return hmac.new(key.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256).hexdigest()


def _client_ip(request):
    try:
        return BaseThrottle().get_ident(request) if request is not None else ""
    except Exception:
        return ""


def _label_for(user):
    from apps.accounts.utils import display_name  # imported here: accounts imports audit

    if user is None:
        return SYSTEM_LABEL
    return sanitize_external_text(display_name(user) or "", max_length=120) or SYSTEM_LABEL


def object_info(obj):
    """(object_type, object_id) for a model instance, or ("", "")."""
    if obj is None:
        return "", ""
    name = obj._meta.model_name
    return TYPE_NAMES.get(name, name), str(obj.pk)


def log(request, action, obj=None, *, actor=None, **metadata):
    """Write one audit entry. Returns it, or None if writing failed (never raises)."""
    try:
        if action not in ACTIONS:
            logger.warning("Audit action %r is not in the catalog (apps/audit/actions.py).", action)
        user = getattr(request, "user", None) if request is not None else None
        if user is None or not getattr(user, "is_authenticated", False):
            user = actor
        object_type, object_id = object_info(obj)
        with transaction.atomic():  # a savepoint when the caller already has a transaction open
            return AuditLog.objects.create(
                actor=user if user is not None and getattr(user, "pk", None) else None,
                actor_label=_label_for(user),
                action=action,
                object_type=object_type,
                object_id=object_id,
                metadata=clean_metadata(metadata),
                ip_hash=hash_ip(_client_ip(request)),
            )
    except Exception:
        logger.exception("Could not write the audit entry %s", action)
        return None

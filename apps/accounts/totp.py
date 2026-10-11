"""Time-based one-time passwords (RFC 6238) and the small crypto helpers around them. Standard library only.

Parameters are the ones every authenticator app supports: HMAC-SHA1, 30 second steps, 6 digits. A code is accepted
for the current step and one step either side (clock drift). Replay protection (a code works once) lives in
apps/accounts/mfa.py, which remembers the last accepted step in the database.

Nothing in this module touches the database, so the RFC test vectors can be checked in isolation.
"""
import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1  # accept the previous, current and next step
SECRET_BYTES = 20  # 160 bits, the size RFC 4226 recommends

# Recovery codes avoid look-alike characters (no i, l, o, 0, 1). Ten characters ~ 49 bits of randomness.
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


# ---------------------------------------------------------------- TOTP
def generate_secret():
    """A new random secret as unpadded base32 (what authenticator apps expect for manual entry)."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii").rstrip("=")


def _key(secret_b32):
    cleaned = re.sub(r"[\s-]", "", secret_b32).upper()
    return base64.b32decode(cleaned + "=" * (-len(cleaned) % 8))


def hotp(key, counter, digits=DIGITS):
    """RFC 4226 HOTP for a raw byte key."""
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % (10**digits)).zfill(digits)


def totp_now(secret_b32, at=None, digits=DIGITS):
    """The code an authenticator app shows at time `at` (seconds since the epoch; default now)."""
    counter = int((time.time() if at is None else at) // STEP_SECONDS)
    return hotp(_key(secret_b32), counter, digits)


def normalise_code(raw):
    """Digits only (people type "123 456"). Anything else yields "" which never matches."""
    text = re.sub(r"[\s-]", "", str(raw or ""))
    return text if text.isdigit() else ""


def matching_step(secret_b32, code, at=None, window=WINDOW):
    """The time step whose code equals `code`, or None.

    Every candidate step is compared (constant time each) without stopping at the first hit, so how long this takes
    does not depend on which step matched.
    """
    code = normalise_code(code)
    if len(code) != DIGITS:
        return None
    key = _key(secret_b32)
    current = int((time.time() if at is None else at) // STEP_SECONDS)
    found = None
    for step in range(max(0, current - window), current + window + 1):
        if hmac.compare_digest(hotp(key, step), code):
            found = step
    return found


def provisioning_uri(secret_b32, account, issuer):
    """otpauth:// link for authenticator apps (shown to the user for manual entry; there is no QR image)."""
    label = f"{quote(issuer, safe='')}:{quote(account, safe='')}"
    query = f"secret={secret_b32}&issuer={quote(issuer, safe='')}&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"
    return f"otpauth://totp/{label}?{query}"


# ---------------------------------------------------------------- recovery codes
def new_recovery_code():
    """Like "k3m9x-q7d2n"."""
    return "-".join("".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(5)) for _ in range(2))


def normalise_recovery_code(raw):
    """Lower case, no spaces or dashes, then re-dashed; "" when it cannot be a recovery code."""
    text = re.sub(r"[\s-]", "", str(raw or "")).lower()
    if len(text) != 10 or any(ch not in _RECOVERY_ALPHABET for ch in text):
        return ""
    return f"{text[:5]}-{text[5:]}"


def looks_like_totp(raw):
    return len(normalise_code(raw)) == DIGITS


# ---------------------------------------------------------------- keyed hashing and encryption at rest
# Everything below derives its keys from a master secret passed in by the caller (settings.MFA_ENCRYPTION_KEY, or
# SECRET_KEY when that is empty), so this module needs no Django settings.
def _derive(master, purpose):
    return hmac.new(master.encode("utf-8"), f"story-platform/mfa/{purpose}/v1".encode("ascii"), hashlib.sha256).digest()


def hash_recovery_code(master, code):
    """Keyed hash of a normalised recovery code (the plain code is shown once and never stored)."""
    return hmac.new(_derive(master, "recovery"), code.encode("ascii"), hashlib.sha256).hexdigest()


def _keystream(key, nonce, length):
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def encrypt_secret(master, plain):
    """Encrypt-then-MAC with HMAC-SHA256 only (no third-party crypto library): a random nonce drives an HMAC
    keystream, and a MAC over nonce + ciphertext detects tampering. Output: "v1." + urlsafe base64."""
    nonce = secrets.token_bytes(16)
    data = plain.encode("utf-8")
    cipher = bytes(a ^ b for a, b in zip(data, _keystream(_derive(master, "enc"), nonce, len(data))))
    tag = hmac.new(_derive(master, "mac"), b"v1" + nonce + cipher, hashlib.sha256).digest()
    return "v1." + base64.urlsafe_b64encode(nonce + cipher + tag).decode("ascii")


def decrypt_secret(master, token):
    """Inverse of encrypt_secret. Raises ValueError when the token is malformed, tampered with, or the key changed."""
    if not isinstance(token, str) or not token.startswith("v1."):
        raise ValueError("Unknown secret format.")
    try:
        raw = base64.urlsafe_b64decode(token[3:].encode("ascii"))
    except Exception as exc:
        raise ValueError("Unreadable secret.") from exc
    if len(raw) < 16 + 32:
        raise ValueError("Unreadable secret.")
    nonce, cipher, tag = raw[:16], raw[16:-32], raw[-32:]
    expected = hmac.new(_derive(master, "mac"), b"v1" + nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("The stored secret cannot be verified (wrong key or tampered data).")
    data = bytes(a ^ b for a, b in zip(cipher, _keystream(_derive(master, "enc"), nonce, len(cipher))))
    return data.decode("utf-8")

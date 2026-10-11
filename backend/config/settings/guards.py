"""Production start-up checks. validate_production() returns a list of problems; production.py refuses to start if
there are any. It takes plain values (no Django settings object) so it can be unit-tested without reloading settings."""
import re

PLACEHOLDER_MARKERS = ("replace-me", "replace_me", "change-me", "changeme", "dev-only", "insecure", "example", "secret-key", "your-secret")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1", "testserver"}


def validate_production(*, secret_key, debug, allowed_hosts, allowed_hosts_from_env, frontend_url, cors_origins, csrf_origins, databases):
    problems = []
    key = secret_key or ""
    if len(key) < 50:
        problems.append("DJANGO_SECRET_KEY must be at least 50 characters (generate one: python -c \"import secrets; print(secrets.token_urlsafe(64))\").")
    elif len(set(key)) < 10:
        problems.append("DJANGO_SECRET_KEY is too repetitive.")
    if any(marker in key.lower() for marker in PLACEHOLDER_MARKERS):
        problems.append("DJANGO_SECRET_KEY still looks like a placeholder from .env.example.")
    if debug:
        problems.append("DEBUG must be off in production.")
    hosts = [h for h in (allowed_hosts or []) if h and h != "*"]
    if not allowed_hosts_from_env or not [h for h in hosts if h not in LOCAL_HOSTS]:
        problems.append("Set DJANGO_ALLOWED_HOSTS to your real domain name(s).")
    if "*" in (allowed_hosts or []):
        problems.append("DJANGO_ALLOWED_HOSTS must not contain '*'.")
    if not str(frontend_url).startswith("https://"):
        problems.append("FRONTEND_URL must start with https://.")
    for name, origins in (("CORS_ALLOWED_ORIGINS", cors_origins), ("CSRF_TRUSTED_ORIGINS", csrf_origins)):
        bad = [o for o in origins if not str(o).startswith("https://")]
        if bad:
            problems.append(f"{name} must all be https:// (found {bad[0]}).")
        if any(o == "*" for o in origins):
            problems.append(f"{name} must not contain '*'.")
    engine = (databases.get("default") or {}).get("ENGINE", "") if databases else ""
    if "postgresql" not in engine:
        problems.append("PostgreSQL is required: set DATABASE_URL (or DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT).")
    return problems


def looks_like_secret(text):
    """Used by the repository secret scan: private keys, AWS-style access keys, long random-looking SECRET_KEY values."""
    patterns = (
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
        r"\bAKIA[0-9A-Z]{16}\b",
    )
    return any(re.search(p, text) for p in patterns)

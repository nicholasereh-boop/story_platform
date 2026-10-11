"""Platform hardening: production guard, headers, CSP report receiver, token lifetimes, CSRF/CORS, endpoint inventory,
secret scanning, log redaction, and the 500 envelope."""
import io
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponse
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.authentication import SessionAuthentication
from rest_framework.test import APIClient

from apps.core import security
from apps.core.permissions import IsStaffUser, IsSuperUser
from apps.core.redaction import RedactingFilter, redact
from config.settings import guards

from .conftest import PASSWORD

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
API = "/api/v1/"

GOOD = dict(
    secret_key="x9Qw-" * 14,  # 70 characters, varied
    debug=False,
    allowed_hosts=["stories.example.com"],
    allowed_hosts_from_env=True,
    frontend_url="https://stories.example.com",
    cors_origins=["https://stories.example.com"],
    csrf_origins=["https://stories.example.com"],
    databases={"default": {"ENGINE": "django.db.backends.postgresql"}},
)


def problems(**changes):
    return guards.validate_production(**{**GOOD, **changes})


# ------------------------------------------------------------------ A1 production guard
def test_a_good_configuration_has_no_problems():
    assert problems() == []


@pytest.mark.parametrize(
    "changes, fragment",
    [
        ({"secret_key": "short"}, "50 characters"),
        ({"secret_key": "replace-me-with-a-long-random-string-" * 3}, "placeholder"),
        ({"secret_key": "a" * 60}, "repetitive"),
        ({"debug": True}, "DEBUG"),
        ({"allowed_hosts": ["localhost", "127.0.0.1"]}, "DJANGO_ALLOWED_HOSTS"),
        ({"allowed_hosts_from_env": False}, "DJANGO_ALLOWED_HOSTS"),
        ({"allowed_hosts": ["*"]}, "'*'"),
        ({"frontend_url": "http://stories.example.com"}, "FRONTEND_URL"),
        ({"cors_origins": ["http://stories.example.com"]}, "CORS_ALLOWED_ORIGINS"),
        ({"csrf_origins": ["http://stories.example.com"]}, "CSRF_TRUSTED_ORIGINS"),
        ({"databases": {"default": {"ENGINE": "django.db.backends.sqlite3"}}}, "PostgreSQL"),
        ({"databases": {}}, "PostgreSQL"),
    ],
)
def test_each_unsafe_setting_is_reported(changes, fragment):
    assert any(fragment in p for p in problems(**changes))


def _manage(*args, **env):
    full = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.production", **env}
    return subprocess.run([sys.executable, "manage.py", *args], cwd=BACKEND, env=full, capture_output=True, text=True, timeout=120)


PROD_ENV = dict(
    DJANGO_SECRET_KEY="prod-" + "k8Zt-QpWm3-" * 8,
    DJANGO_ALLOWED_HOSTS="stories.example.com",
    FRONTEND_URL="https://stories.example.com",
    DATABASE_URL="postgresql://story:pw@localhost:5432/story",
    DB_NAME="",
)


def test_production_refuses_to_start_when_unsafe():
    result = _manage("check", DJANGO_SECRET_KEY="short", DJANGO_ALLOWED_HOSTS="stories.example.com",
                     FRONTEND_URL="https://stories.example.com", DATABASE_URL="postgresql://u:p@localhost/db")
    assert result.returncode != 0 and "Unsafe production configuration" in result.stderr


def test_check_deploy_passes_with_no_warnings_in_production():
    result = _manage("check", "--deploy", "--fail-level", "WARNING", **PROD_ENV)
    assert result.returncode == 0, result.stderr + result.stdout


# ------------------------------------------------------------------ A2 headers
def assert_headers(response, csp_fragment="default-src 'none'"):
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response["Permissions-Policy"] and "microphone=()" in response["Permissions-Policy"]
    assert "geolocation=()" in response["Permissions-Policy"]
    assert response["Cross-Origin-Opener-Policy"] == "same-origin-allow-popups"
    assert response["X-Frame-Options"] == "DENY"
    csp = response.get("Content-Security-Policy") or response.get("Content-Security-Policy-Report-Only")
    assert csp and csp_fragment in csp and "frame-ancestors 'none'" in csp


def test_api_responses_carry_every_security_header(client, db):
    assert_headers(client.get(API + "health/"))
    assert_headers(client.get(API + "stories/"))
    assert_headers(client.get(API + "no-such-endpoint/"))  # the JSON 404


def test_error_responses_carry_the_headers_too(client, monkeypatch, db):
    from apps.core import views

    monkeypatch.setattr(views.HealthView, "get", lambda self, request, *a, **k: 1 / 0)
    r = client.get(API + "health/")
    assert r.status_code == 500
    assert_headers(r)


def test_media_gets_a_sandboxed_policy_and_nosniff(rf):
    middleware = security.SecurityHeadersMiddleware(lambda request: HttpResponse("img"))
    r = middleware(rf.get(settings.MEDIA_URL + "uploads/2026/01/a.png"))
    assert r["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in r["Content-Security-Policy"] and "default-src 'none'" in r["Content-Security-Policy"]


def test_django_admin_policy_allows_only_its_own_origin():
    policy = security.policy_for("/" + settings.DJANGO_ADMIN_URL + "login/")
    assert "default-src 'self'" in policy and "frame-ancestors 'none'" in policy and "http" not in policy


def test_report_only_mode_switches_the_header_name(client, settings, db):
    settings.CSP_REPORT_ONLY = True
    r = client.get(API + "health/")
    assert "Content-Security-Policy-Report-Only" in r and "Content-Security-Policy" not in r


def test_hsts_is_configured_for_production_settings():
    text = (BACKEND / "config/settings/production.py").read_text()
    assert "SECURE_HSTS_SECONDS = 31536000" in text and "SECURE_HSTS_INCLUDE_SUBDOMAINS = True" in text


# ------------------------------------------------------------------ A2 CSP report receiver
def test_csp_report_is_accepted_logged_and_trimmed(client, caplog, db):
    caplog.set_level(logging.WARNING, logger="csp")
    body = {"csp-report": {
        "document-uri": "https://site.example/read/a-story?token=SECRET&email=a@b.co#frag",
        "violated-directive": "script-src-elem",
        "blocked-uri": "https://evil.example/x.js?uid=42",
        "referrer": "https://secret-referrer.example/private",
        "script-sample": "alert(document.cookie)",
        "original-policy": "default-src 'none'",
    }}
    r = client.generic("POST", API + "csp-report/", json.dumps(body), content_type="application/csp-report")
    assert r.status_code == 204
    logged = caplog.text
    assert "script-src-elem" in logged and "https://evil.example/x.js" in logged
    for leak in ("SECRET", "a@b.co", "uid=42", "secret-referrer", "alert(", "original-policy"):
        assert leak not in logged


def test_csp_report_never_fails_on_garbage(client, db):
    for payload in ("not json", "[]", "{}", "null"):
        r = client.generic("POST", API + "csp-report/", payload, content_type="application/json")
        assert r.status_code in (204, 400)
    assert client.get(API + "csp-report/").status_code == 405


def test_csp_report_is_rate_limited(db):
    codes = [APIClient().post(API + "csp-report/", {"csp-report": {"violated-directive": "x"}}, format="json").status_code for _ in range(31)]
    assert codes[:30] == [204] * 30 and codes[30] == 429


# ------------------------------------------------------------------ A3 cookies and tokens
def test_cookie_flags(client, db):
    assert settings.SESSION_COOKIE_HTTPONLY is True and settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.CSRF_COOKIE_SAMESITE == "Lax"
    assert settings.CSRF_COOKIE_HTTPONLY is False  # React must read it to send X-CSRFToken
    text = (BACKEND / "config/settings/production.py").read_text()
    assert "SESSION_COOKIE_SECURE = True" in text and "CSRF_COOKIE_SECURE = True" in text


def test_token_lifetimes_are_one_hour_and_three_days():
    assert settings.PASSWORD_RESET_TIMEOUT == 3600
    assert settings.ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS == 3


def reset_link(user):
    return {"uid": urlsafe_base64_encode(force_bytes(user.pk)), "token": default_token_generator.make_token(user)}


def test_expired_reset_token_fails(client, user, settings):
    link = reset_link(user)
    settings.PASSWORD_RESET_TIMEOUT = -1  # everything is already older than the limit
    r = client.post(API + "auth/password/reset/confirm/", {**link, "password": "Another-long-pass-77"}, format="json")
    assert r.status_code == 400


def test_reset_token_cannot_be_used_twice(client, user):
    link = reset_link(user)
    first = client.post(API + "auth/password/reset/confirm/", {**link, "password": "Another-long-pass-77"}, format="json")
    second = client.post(API + "auth/password/reset/confirm/", {**link, "password": "Yet-another-pass-88"}, format="json")
    assert first.status_code == 200 and second.status_code == 400


def test_expired_and_reused_verification_links_fail(client, user, settings):
    from allauth.account.models import EmailAddress, EmailConfirmationHMAC

    address = EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)
    key = EmailConfirmationHMAC(address).key
    settings.ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = -1
    assert client.post(API + "auth/email/verify/", {"key": key}, format="json").status_code == 400  # expired
    settings.ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
    assert client.post(API + "auth/email/verify/", {"key": key}, format="json").status_code == 200
    assert client.post(API + "auth/email/verify/", {"key": key}, format="json").status_code == 400  # already used


# ------------------------------------------------------------------ A4 CSRF and CORS
def iter_routes(patterns=None, prefix=""):
    for p in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(p, URLResolver):
            yield from iter_routes(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p.callback


UNSAFE = ("post", "put", "patch", "delete")


def drf_views():
    for route, callback in iter_routes():
        cls = getattr(callback, "cls", None)
        if cls is not None:
            yield route, cls


def unsafe_methods(cls):
    return [m for m in UNSAFE if m in cls.http_method_names and hasattr(cls, m)]


def enforces_csrf(cls):
    return any(issubclass(a, SessionAuthentication) for a in cls.authentication_classes)


CSRF_EXEMPT_ROUTES = {"analytics/collect/", "csp-report/"}  # both write only anonymous data


def test_the_only_csrf_exempt_views_are_the_two_anonymous_collectors():
    exempt = {route for route, cls in drf_views() if unsafe_methods(cls) and not enforces_csrf(cls)}
    short = {re.sub(r"^.*?v1\)/", "", r) for r in exempt}
    assert short == CSRF_EXEMPT_ROUTES, f"unexpected CSRF-exempt views: {short ^ CSRF_EXEMPT_ROUTES}"


def test_no_plain_django_view_is_csrf_exempt():
    leaks = [route for route, cb in iter_routes() if getattr(cb, "csrf_exempt", False) and getattr(cb, "cls", None) is None]
    assert leaks == []


def test_csrf_is_enforced_for_anonymous_posts(db):
    strict = APIClient(enforce_csrf_checks=True)
    r = strict.post(API + "auth/login/", {"email": "a@b.co", "password": "x"}, format="json")
    assert r.status_code == 403
    strict.get(API + "auth/csrf/")
    token = strict.cookies["csrftoken"].value
    r = strict.post(API + "auth/login/", {"email": "a@b.co", "password": "x"}, format="json", HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 400  # past CSRF: wrong credentials


def test_csrf_is_enforced_for_logged_in_users(user, db):
    strict = APIClient(enforce_csrf_checks=True)
    strict.force_login(user)
    assert strict.post(API + "auth/logout/").status_code == 403


def test_hostile_origin_gets_no_cors_headers(client, db):
    r = client.get(API + "health/", HTTP_ORIGIN="https://evil.example")
    assert "Access-Control-Allow-Origin" not in r and "Access-Control-Allow-Credentials" not in r
    pre = client.options(API + "auth/login/", HTTP_ORIGIN="https://evil.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
    assert "Access-Control-Allow-Origin" not in pre


def test_only_the_frontend_origin_is_allowed(client, db):
    r = client.get(API + "health/", HTTP_ORIGIN=settings.FRONTEND_URL)
    assert r["Access-Control-Allow-Origin"] == settings.FRONTEND_URL and r["Access-Control-Allow-Credentials"] == "true"
    assert "*" not in settings.CORS_ALLOWED_ORIGINS and settings.CORS_ALLOW_ALL_ORIGINS is False


# ------------------------------------------------------------------ A5 endpoint inventory
def explicit_permissions(cls):
    return any("permission_classes" in vars(k) for k in cls.__mro__ if not k.__module__.startswith("rest_framework"))


def test_every_api_view_declares_its_permissions():
    missing = [route for route, cls in drf_views() if not explicit_permissions(cls)]
    assert missing == []


def test_every_admin_endpoint_is_staff_only():
    wrong = []
    for route, cls in drf_views():
        if route.split("v1)/", 1)[-1].startswith("admin/"):
            if not any(issubclass(p, (IsStaffUser, IsSuperUser)) for p in cls.permission_classes):
                wrong.append(route)
    assert wrong == []


def test_unauthenticated_writes_are_always_throttled():
    from rest_framework.permissions import AllowAny

    unthrottled = []
    for route, cls in drf_views():
        if unsafe_methods(cls) and any(issubclass(p, AllowAny) for p in cls.permission_classes):
            if not getattr(cls, "throttle_scope", None):
                unthrottled.append(route)
    assert unthrottled == []


def test_every_throttle_scope_in_use_has_a_rate():
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    for scope in ("admin_write", "mfa", "data_export", "account_delete", "csp_report", "password_change", "logout", "email_verify"):
        assert scope in rates
    assert rates["mfa"] == "10/10min" and rates["data_export"] == "3/hour" and rates["account_delete"] == "3/hour"
    assert rates["admin_write"] == "300/min" and rates["csp_report"] == "30/min"


def test_admin_writes_are_throttled_per_staff_user(staff_client, settings, db, monkeypatch):
    from apps.core import throttles

    monkeypatch.setitem(throttles.AdminWriteThrottle.THROTTLE_RATES, "admin_write", "3/min")
    codes = [staff_client.post(API + "admin/tags/", {"name": f"t{i}"}, format="json").status_code for i in range(5)]
    assert codes[:3] == [201] * 3 and 429 in codes[3:]
    assert staff_client.get(API + "admin/tags/").status_code == 200  # reads are never limited by this scope


# ------------------------------------------------------------------ A7 errors and logging
def capture_logs():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    return stream, handler


def test_redaction_removes_secrets():
    text = ("login failed password=hunter2 token: abc123 'sessionid': 'xyz' for bob@example.com "
            "Authorization: Bearer abcdef.ghi Cookie: sessionid=zzz; csrftoken=yyy url=/x?email=al%40ex.org&new_password=s3cret")
    cleaned = redact(text)
    for leak in ("hunter2", "abc123", "xyz", "bob@example.com", "abcdef.ghi", "zzz", "yyy", "al%40ex.org", "s3cret"):
        assert leak not in cleaned


def test_every_log_handler_redacts():
    assert settings.LOGGING["handlers"]
    for name, handler in settings.LOGGING["handlers"].items():
        assert "redact" in handler.get("filters", []), name
    assert settings.LOGGING["filters"]["redact"]["()"] == "apps.core.redaction.RedactingFilter"


def test_a_failing_view_returns_the_envelope_without_a_traceback_or_secret(client, monkeypatch, db):
    from apps.core import views

    def boom(self, request, *a, **k):
        raise RuntimeError("database password=hunter2 for admin@example.com exploded")

    monkeypatch.setattr(views.HealthView, "get", boom)
    stream, handler = capture_logs()
    try:
        r = client.get(API + "health/")
    finally:
        logging.getLogger().removeHandler(handler)
    body = r.json()
    assert r.status_code == 500 and body["data"] is None
    assert re.fullmatch(r"[0-9a-f]{8}", body["errors"]["error_id"])
    assert body["errors"]["error_id"] in body["message"]
    raw = r.content.decode()
    for leak in ("Traceback", "RuntimeError", "hunter2", "admin@example.com", "File \"", "SECRET_KEY"):
        assert leak not in raw
    logged = stream.getvalue()
    assert body["errors"]["error_id"] in logged and "hunter2" not in logged and "admin@example.com" not in logged


def test_a_wrong_password_login_leaves_no_secret_in_any_log(client, user, caplog):
    caplog.set_level(logging.DEBUG)
    stream, handler = capture_logs()
    try:
        client.post(API + "auth/login/", {"email": user.email, "password": "Wr0ng-Passw0rd-xyz"}, format="json")
    finally:
        logging.getLogger().removeHandler(handler)
    assert "Wr0ng-Passw0rd-xyz" not in caplog.text and "Wr0ng-Passw0rd-xyz" not in stream.getvalue()


# ------------------------------------------------------------------ A8 secrets hygiene
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", "staticfiles", "media", ".pytest_cache", "coverage"}
TEXT_SUFFIXES = {".py", ".js", ".jsx", ".json", ".md", ".yml", ".yaml", ".txt", ".cfg", ".toml", ".html", ".css", ".ini", ".example", ".env", ".sh"}


def repo_files(base):
    for path in base.rglob("*"):
        if path.is_file() and not (set(path.relative_to(base).parts) & SKIP_DIRS) and (path.suffix in TEXT_SUFFIXES or path.name.startswith(".env")):
            yield path


def test_frontend_never_references_server_side_secrets():
    pattern = re.compile(r"GOOGLE_CLIENT_SECRET|SECRET_KEY|\b[A-Z0-9_]*_SECRET\b|\b[A-Z0-9_]*_PASSWORD\b|MFA_ENCRYPTION_KEY")
    files = list((ROOT / "frontend" / "src").rglob("*.js*")) + [ROOT / "frontend" / n for n in ("vite.config.js", "index.html") if (ROOT / "frontend" / n).exists()]
    hits = [f"{p.relative_to(ROOT)}: {m.group(0)}" for p in files if "__tests__" not in p.parts for m in pattern.finditer(p.read_text(errors="ignore"))]
    assert hits == []


def test_frontend_env_files_only_expose_public_variables():
    for name in (".env.example", ".env.production.example"):
        path = ROOT / "frontend" / name
        if path.exists():
            for line in path.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    assert line.split("=")[0].strip().startswith("VITE_"), line


def test_repository_contains_no_obvious_committed_secrets():
    key_assignment = re.compile(r"""SECRET_KEY\s*=\s*['"][A-Za-z0-9!@#$%^&*()\-_=+/]{40,}['"]""")
    found = []
    for path in repo_files(ROOT):
        if path.name == ".env.example" or path.name == "test_security_settings.py":
            continue
        text = path.read_text(errors="ignore")
        if guards.looks_like_secret(text) or key_assignment.search(text):
            found.append(str(path.relative_to(ROOT)))
    assert found == []


def test_a_real_looking_secret_is_detected():
    assert guards.looks_like_secret("AKIA" + "ABCDEFGHIJKLMNOP")
    assert guards.looks_like_secret("-----BEGIN " + "RSA PRIVATE KEY-----")
    assert not guards.looks_like_secret("nothing to see here")


def test_django_admin_path_is_configurable_and_can_be_off():
    assert settings.DJANGO_ADMIN_URL.endswith("/") and settings.DJANGO_ADMIN_ENABLED in (True, False)
    text = (BACKEND / "config/urls.py").read_text()
    assert "DJANGO_ADMIN_ENABLED" in text and "settings.DJANGO_ADMIN_URL" in text


# ------------------------------------------------------------------ privacy config endpoints
def test_public_config_exposes_no_secrets(client, db):
    data = client.get(API + "public-config/").json()["data"]
    assert set(data) == {"site_name", "consent_mode", "analytics_enabled", "contact_email"}
    assert data["consent_mode"] in ("notice", "opt_in", "opt_out")
    raw = json.dumps(data)
    assert settings.SECRET_KEY not in raw


def test_privacy_policy_numbers_come_from_the_real_settings(client, settings, db):
    settings.ANALYTICS_RETENTION_DAYS = 120
    settings.AUDIT_RETENTION_DAYS = 400
    settings.SITE_CONTACT_EMAIL = "privacy@example.org"
    data = client.get(API + "privacy-policy/").json()["data"]
    assert data["retention"]["analytics_events_days"] == 120 and data["retention"]["audit_log_days"] == 400
    assert data["contact_email"] == "privacy@example.org"


def test_cookie_table_matches_the_cookies_the_backend_really_sets(client, user, db):
    from apps.core.views import cookie_table

    names = {c["name"] for c in cookie_table()}
    assert names == {"sessionid", "csrftoken"} and all(c["necessary"] for c in cookie_table())
    seen = set()
    for response in (client.get(API + "auth/csrf/"), client.post(API + "auth/login/", {"email": user.email, "password": PASSWORD}, format="json"),
                     client.get(API + "stories/"), client.get(API + "public-config/"), client.post(API + "analytics/collect/", {}, format="json")):
        seen |= set(response.cookies)
    assert seen <= names
    assert client.get(API + "privacy-policy/").json()["data"]["cookies"]

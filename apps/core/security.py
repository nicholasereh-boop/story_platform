"""Security response headers and the Content-Security-Policy for everything Django itself serves.

Django serves the API (JSON), the built-in admin, allauth redirects and, in development only, uploaded media.
The React app is static files served by Nginx (Phase 12); the CSP for THAT lives in docs/SECURITY.md as a ready-to-paste
snippet, because Django never sees those responses.

Headers set by Django's own SecurityMiddleware (configured in settings): X-Content-Type-Options, Referrer-Policy,
Cross-Origin-Opener-Policy and, in production, HSTS. XFrameOptionsMiddleware adds X-Frame-Options. This middleware adds
Permissions-Policy and the Content-Security-Policy, and repeats the cheap ones with setdefault() so a missing setting can
never silently drop them.
"""
from django.conf import settings

REPORT_URI = "/api/v1/csp-report/"
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"

# JSON API and anything else Django answers: nothing may load, nothing may frame it.
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# The built-in Django admin needs its own CSS, JS and inline styles; still no framing and no outside origins.
DJANGO_ADMIN_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
# Uploaded files viewed directly in the browser: they can show an image and nothing else, and are sandboxed.
MEDIA_CSP = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox; frame-ancestors 'none'"
# Swagger UI (/api/v1/docs/) loads its scripts and styles from a CDN.
DOCS_CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self'; frame-ancestors 'none'"
)


def policy_for(path):
    """The CSP (without the report-uri) that applies to a request path."""
    if path.startswith("/api/v1/docs/"):
        return DOCS_CSP
    if path.startswith("/" + settings.DJANGO_ADMIN_URL):
        return DJANGO_ADMIN_CSP
    media = settings.MEDIA_URL if settings.MEDIA_URL.startswith("/") else None
    if media and path.startswith(media):
        return MEDIA_CSP
    return API_CSP


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("Referrer-Policy", settings.SECURE_REFERRER_POLICY or "strict-origin-when-cross-origin")
        headers.setdefault("Cross-Origin-Opener-Policy", settings.SECURE_CROSS_ORIGIN_OPENER_POLICY or "same-origin-allow-popups")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        name = "Content-Security-Policy-Report-Only" if settings.CSP_REPORT_ONLY else "Content-Security-Policy"
        if name not in headers:
            headers[name] = f"{policy_for(request.path_info)}; report-uri {REPORT_URI}"
        return response

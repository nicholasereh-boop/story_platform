import logging
from urllib.parse import urlsplit

from django.conf import settings
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .permissions import IsStaffUser

csp_logger = logging.getLogger("csp")


class HealthView(APIView):
    """Liveness check for load balancers and uptime monitors."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request, *args, **kwargs):
        return Response({"status": "ok"})


class AdminPingView(APIView):
    """Tiny staff-only endpoint so the permission layer can be tested before any admin features exist."""

    permission_classes = [IsStaffUser]

    def get(self, request, *args, **kwargs):
        return Response({"admin": True})


class PublicConfigView(APIView):
    """GET /api/v1/public-config/ : the few site settings the browser needs before anything else. No secrets, ever."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_read"
    http_method_names = ["get", "head", "options"]

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "site_name": settings.SITE_NAME,
                "consent_mode": settings.PRIVACY_CONSENT_MODE,
                "analytics_enabled": settings.ANALYTICS_ENABLED,
                "contact_email": settings.SITE_CONTACT_EMAIL,
            }
        )


def cookie_table():
    """Every cookie the backend sets. The privacy page shows this table, and a test keeps it in step with the settings."""
    return [
        {
            "name": settings.SESSION_COOKIE_NAME,
            "purpose": "Keeps you logged in.",
            "duration": f"{settings.SESSION_COOKIE_AGE // 86400} days (staff: ends after {settings.STAFF_SESSION_IDLE_MINUTES} minutes of inactivity)",
            "necessary": True,
        },
        {
            "name": settings.CSRF_COOKIE_NAME,
            "purpose": "Protects forms and actions against forged requests.",
            "duration": f"{settings.CSRF_COOKIE_AGE // 86400} days",
            "necessary": True,
        },
    ]


class PrivacyPolicyView(APIView):
    """GET /api/v1/privacy-policy/ : the numbers and names the privacy page prints, taken from the live settings so the
    page can never promise something the server does not do. (Legal wording stays in the frontend and needs owner review.)"""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_read"
    http_method_names = ["get", "head", "options"]

    def get(self, request, *args, **kwargs):
        from apps.analytics.purge import VISITOR_RETENTION_DAYS, retention_days as analytics_days
        from apps.audit.retention import retention_days as audit_days

        return Response(
            {
                "site_name": settings.SITE_NAME,
                "operator_name": settings.SITE_OPERATOR_NAME,
                "contact_email": settings.SITE_CONTACT_EMAIL,
                "effective_date": settings.PRIVACY_POLICY_DATE,
                "consent_mode": settings.PRIVACY_CONSENT_MODE,
                "analytics_enabled": settings.ANALYTICS_ENABLED,
                "retention": {
                    "analytics_events_days": analytics_days(),
                    "analytics_visitors_days": VISITOR_RETENTION_DAYS,
                    "audit_log_days": audit_days(),
                    "comment_edit_window_minutes": settings.COMMENT_EDIT_WINDOW_MINUTES,
                },
                "cookies": cookie_table(),
            }
        )


class CspReportParser(JSONParser):
    media_type = "application/csp-report"  # what browsers send for the report-uri directive


class ReportsJsonParser(JSONParser):
    media_type = "application/reports+json"  # the newer Reporting API format


_REPORT_FIELDS = (
    "violated-directive", "effective-directive", "disposition", "status-code", "line-number", "column-number",
    "violatedDirective", "effectiveDirective", "statusCode", "lineNumber", "columnNumber",
)
_URL_FIELDS = ("document-uri", "blocked-uri", "source-file", "documentURL", "blockedURL", "sourceFile")


def _path_only(value):
    """origin + path of a URL, with query and fragment dropped (they can carry tokens or personal data)."""
    text = str(value or "")[:400]
    if "://" not in text:
        return text[:200]  # "inline", "eval", "self" ...
    parts = urlsplit(text)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"[:200]


def trim_report(body):
    """Keep only a few harmless fields of a CSP report. Never the referrer, the script sample or the full policy."""
    if isinstance(body, dict) and isinstance(body.get("csp-report"), dict):
        body = body["csp-report"]
    if isinstance(body, list):
        body = (body[0] or {}).get("body", {}) if body and isinstance(body[0], dict) else {}
    if not isinstance(body, dict):
        return {}
    out = {key: str(body[key])[:120] for key in _REPORT_FIELDS if key in body}
    out.update({key: _path_only(body[key]) for key in _URL_FIELDS if key in body})
    return out


class CspReportView(APIView):
    """POST /api/v1/csp-report/ : receives browser CSP violation reports and writes a trimmed line to the log.

    Anonymous and exempt from CSRF on purpose (browsers send these without any token), so it only ever LOGS: it stores
    nothing and answers 204 whatever it receives. Rate limited per IP (csp_report)."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "csp_report"
    parser_classes = [CspReportParser, ReportsJsonParser, JSONParser]
    http_method_names = ["post", "options"]

    def post(self, request, *args, **kwargs):
        try:
            report = trim_report(request.data)
        except Exception:  # unparseable body: nothing to log
            report = {}
        if report:
            csp_logger.warning("CSP violation report: %s", report)
        return Response(status=204)

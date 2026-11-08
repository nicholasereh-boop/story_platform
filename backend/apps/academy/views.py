from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class AcademyConfigView(APIView):
    """GET: what the Academy pages need to describe themselves truthfully. Nothing private."""

    permission_classes = [AllowAny]
    throttle_scope = "public_read"

    def get_permissions(self):
        from .permissions import AcademyEnabled

        return [AcademyEnabled(), AllowAny()]

    def get(self, request, **kwargs):
        return Response({
            "enabled": True,
            "currency": settings.ACADEMY_CURRENCY,
            "comment_gate_default": settings.ACADEMY_COMMENT_GATE_DEFAULT,
            "default_completion_threshold": settings.ACADEMY_DEFAULT_COMPLETION_THRESHOLD,
            "progress_update_interval_seconds": settings.ACADEMY_PROGRESS_UPDATE_INTERVAL_SECONDS,
            "payments_enabled": bool(settings.PAYSTACK_SECRET_KEY),
        })
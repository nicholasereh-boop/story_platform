from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsStaffUser


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

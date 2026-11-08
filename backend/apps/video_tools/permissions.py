from django.conf import settings
from django.http import Http404
from rest_framework.permissions import BasePermission, IsAuthenticated


class VideoToolsEnabled(BasePermission):
    """VIDEO_TOOLS_ENABLED=false makes every endpoint answer 404."""

    def has_permission(self, request, view):
        if not settings.VIDEO_TOOLS_ENABLED:
            raise Http404()
        return True


class IsActiveUser(IsAuthenticated):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)

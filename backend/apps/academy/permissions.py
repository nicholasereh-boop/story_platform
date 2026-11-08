from django.conf import settings
from django.http import Http404
from rest_framework.permissions import BasePermission, IsAuthenticated


class AcademyEnabled(BasePermission):
    """The whole Academy can be switched off (ACADEMY_ENABLED=false): every endpoint then answers 404, like a page that does not exist."""

    def has_permission(self, request, view):
        if not settings.ACADEMY_ENABLED:
            raise Http404()
        return True


class IsActiveUser(IsAuthenticated):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
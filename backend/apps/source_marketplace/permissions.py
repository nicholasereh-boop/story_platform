from django.conf import settings
from django.http import Http404
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated


class MarketplaceEnabled(BasePermission):
    """The whole feature can be switched off (MARKETPLACE_ENABLED=false): every endpoint then answers 404."""

    def has_permission(self, request, view):
        if not settings.MARKETPLACE_ENABLED:
            raise Http404()
        return True


class IsActiveUser(IsAuthenticated):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class IsProjectOwner(BasePermission):
    """Object-level: only the seller who owns the project. Staff do NOT edit sellers' projects; they moderate them
    through /admin/marketplace/, which can approve, reject or archive but never changes the seller's content."""

    def has_object_permission(self, request, view, obj):
        project = getattr(obj, "project", obj)
        return bool(request.user and request.user.is_authenticated and project.owner_id == request.user.pk)


class PublicReadOrActive(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return IsActiveUser().has_permission(request, view)

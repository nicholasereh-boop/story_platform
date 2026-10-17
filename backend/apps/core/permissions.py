from rest_framework.permissions import BasePermission


class IsStaffUser(BasePermission):
    """Security boundary for every /admin/* endpoint (the React admin UI is only a convenience)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)


class IsSuperUser(BasePermission):
    """Only superusers may grant or remove staff access (used by the user-management endpoint in a later phase)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


class IsOwnerOrStaff(BasePermission):
    """Object-level: the owner (obj.user or obj.created_by) or any staff member."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "created_by", None)
        return owner is not None and owner == user


class IsVerifiedEmail(BasePermission):
    """Ready for later phases (e.g. commenting): requires a verified email address."""

    message = "Please verify your email address first."

    def has_permission(self, request, view):
        from allauth.account.models import EmailAddress

        user = request.user
        if not (user and user.is_authenticated):
            return False
        return EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists()

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


def require_two_step(request):
    """Staff-level two-step check (TOTP), done HERE in the permission layer on every request, not only at login, so a
    Google login or a stolen session cookie cannot skip it. Raises a 403 whose body carries a machine-readable code:
      "mfa_required"        the account has two-step verification but this session has not passed it
      "mfa_setup_required"  STAFF_MFA_REQUIRED is on and the account has no device yet
    Does nothing when MFA is off (the default) and the account has no device."""
    from apps.accounts import mfa  # imported here: accounts imports this module

    problem = mfa.enforcement_problem(request, request.user)
    if problem:
        raise PermissionDenied({"detail": mfa.MESSAGES[problem], "code": problem})
    return True


class IsStaffUser(BasePermission):
    """Security boundary for every /admin/* endpoint (the React admin UI is only a convenience)."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active and user.is_staff):
            return False
        return require_two_step(request)


class IsSuperUser(BasePermission):
    """Only superusers may grant or remove staff access (the user-management endpoints, Phase 10)."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active and user.is_superuser):
            return False
        return require_two_step(request)


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

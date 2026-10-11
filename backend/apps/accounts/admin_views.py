"""Staff user management, mounted under /api/v1/admin/users/.

Rules (enforced HERE, not only in the React UI):
  - staff can list and view users, activate/deactivate readers and staff, end sessions and re-send verification mail
  - only a SUPERUSER can grant or remove the staff role
  - staff cannot touch superuser accounts at all; the superuser flag itself can never be changed through the API
  - nobody can deactivate or demote themselves
  - the last active superuser can never be deactivated
  - passwords, hashes, MFA secrets and session keys are never returned
"""
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import service as audit
from apps.core.permissions import IsStaffUser, IsSuperUser

from . import privacy, sessions
from .models import MFADevice
from .services import get_profile, is_email_verified, send_verification_email

User = get_user_model()
ALLOWED_FIELDS = {"is_active", "is_staff"}
ORDERINGS = {"date_joined", "last_login", "email", "comment_count", "like_count"}


def role_of(user):
    return "superuser" if user.is_superuser else "staff" if user.is_staff else "reader"


def user_queryset():
    return User.objects.select_related("profile").annotate(
        comment_count=Count("comments", filter=Q(comments__status="approved"), distinct=True),
        like_count=Count("likes", distinct=True),
        mfa_enabled=Exists(MFADevice.objects.filter(user=OuterRef("pk"), confirmed_at__isnull=False)),
        email_is_verified=Exists(EmailAddress.objects.filter(user=OuterRef("pk"), email__iexact=OuterRef("email"), verified=True)),
    )


class AdminUserSerializer(serializers.ModelSerializer):
    """Read-only. An explicit allowlist of fields: no password, hash, secret or session key can appear here."""

    display_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()
    comment_count = serializers.IntegerField(read_only=True)
    like_count = serializers.IntegerField(read_only=True)
    mfa_enabled = serializers.BooleanField(read_only=True)
    anonymised = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "display_name", "role", "is_active", "is_staff", "is_superuser", "email_verified",
            "date_joined", "last_login", "comment_count", "like_count", "mfa_enabled", "anonymised",
        ]
        read_only_fields = fields

    def get_display_name(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.display_name if profile else get_profile(obj).display_name

    def get_role(self, obj):
        return role_of(obj)

    def get_email_verified(self, obj):
        value = getattr(obj, "email_is_verified", None)
        return is_email_verified(obj) if value is None else bool(value)

    def get_anonymised(self, obj):
        return privacy.is_anonymised(obj)


def bool_param(params, name):
    value = params.get(name)
    return None if value in (None, "") else str(value).lower() in ("1", "true", "yes")


class AdminUserListView(generics.ListAPIView):
    """Filters: ?role=reader|staff|superuser, ?active=1|0, ?verified=1|0, ?q= (email or display name), ?ordering=."""

    permission_classes = [IsStaffUser]
    serializer_class = AdminUserSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        params = self.request.query_params
        qs = user_queryset()
        role = params.get("role")
        if role:
            filters = {"reader": Q(is_staff=False, is_superuser=False), "staff": Q(is_staff=True, is_superuser=False), "superuser": Q(is_superuser=True)}
            if role not in filters:
                raise serializers.ValidationError({"role": ["Unknown role."], "detail": ["Unknown role."]})
            qs = qs.filter(filters[role])
        active = bool_param(params, "active")
        if active is not None:
            qs = qs.filter(is_active=active)
        verified = bool_param(params, "verified")
        if verified is not None:
            qs = qs.filter(email_is_verified=verified)
        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(profile__display_name__icontains=q))
        ordering = params.get("ordering") or "-date_joined"
        if ordering.lstrip("-") not in ORDERINGS:
            ordering = "-date_joined"
        return qs.order_by(ordering, "-id")


class AdminUserDetailView(APIView):
    """GET one user. PATCH accepts ONLY {is_active, is_staff}; any other key is refused (is_superuser can never be changed)."""

    permission_classes = [IsStaffUser]
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request, pk, *args, **kwargs):
        return Response(AdminUserSerializer(get_object_or_404(user_queryset(), pk=pk)).data)

    def patch(self, request, pk, *args, **kwargs):
        target = get_object_or_404(User, pk=pk)
        body = request.data if isinstance(request.data, dict) else {}
        unknown = sorted(set(body) - ALLOWED_FIELDS)
        if unknown or not body:
            message = "Only is_active and is_staff can be changed here." if unknown else "Send is_active and/or is_staff."
            raise serializers.ValidationError({"detail": [message], "fields": [message]})
        for name in body:
            if not isinstance(body[name], bool):
                raise serializers.ValidationError({name: ["Send true or false."], "detail": ["Send true or false."]})
        changes = {name: value for name, value in body.items() if getattr(target, name) != value}
        actor = request.user

        if target.is_superuser and not actor.is_superuser:
            raise PermissionDenied("Staff cannot change superuser accounts.")
        if "is_staff" in changes and not IsSuperUser().has_permission(request, self):
            raise PermissionDenied("Only a superuser can grant or remove the staff role.")
        if target.pk == actor.pk and (changes.get("is_active") is False or changes.get("is_staff") is False):
            raise serializers.ValidationError({"detail": ["You cannot deactivate or demote yourself."]})
        if target.is_superuser and "is_staff" in changes:
            raise serializers.ValidationError({"detail": ["A superuser always has the staff role. The superuser flag cannot be changed here."]})
        if changes.get("is_active") is False and privacy.is_last_active_superuser(target):
            raise serializers.ValidationError({"detail": ["This is the only active superuser. Make another superuser first."]})
        if privacy.is_anonymised(target):
            raise serializers.ValidationError({"detail": ["This account was deleted by its owner and cannot be changed."]})

        if changes:
            with transaction.atomic():
                before = {name: getattr(target, name) for name in changes}
                for name, value in changes.items():
                    setattr(target, name, value)
                target.save(update_fields=list(changes))
                if changes.get("is_active") is False or changes.get("is_staff") is False:
                    sessions.revoke_all(target)  # deactivated or demoted users are signed out at once
                audit.log(request, "user.update", target, changes={n: [before[n], v] for n, v in changes.items()})
        return Response(AdminUserSerializer(get_object_or_404(user_queryset(), pk=pk)).data)


def _writable_target(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.is_superuser and not request.user.is_superuser:
        raise PermissionDenied("Staff cannot change superuser accounts.")
    return target


class AdminUserRevokeSessionsView(APIView):
    permission_classes = [IsStaffUser]
    http_method_names = ["post", "options"]

    def post(self, request, pk, *args, **kwargs):
        target = _writable_target(request, pk)
        with transaction.atomic():
            ended = sessions.revoke_all(target)
            audit.log(request, "user.sessions_revoked", target, ended=ended)
        return Response({"message": f"Signed out of {ended} session(s).", "ended": ended})


class AdminUserResendVerificationView(APIView):
    permission_classes = [IsStaffUser]
    http_method_names = ["post", "options"]

    def post(self, request, pk, *args, **kwargs):
        target = _writable_target(request, pk)
        if not target.is_active or privacy.is_anonymised(target):
            raise serializers.ValidationError({"detail": ["This account is not active."]})
        sent = send_verification_email(request._request, target)
        if not sent:
            return Response({"message": "This address is already verified.", "sent": False})
        audit.log(request, "user.verification_resent", target)
        return Response({"message": "Verification email sent.", "sent": True})

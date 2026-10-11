import math

from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied, Throttled
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import service as audit
from apps.core.throttles import FlexibleScopedRateThrottle

from . import mfa, privacy, sessions
from .models import UserSession
from .serializers import (
    AccountDeleteSerializer,
    CodeSerializer,
    EmailVerifySerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    SensitiveActionSerializer,
    UserSerializer,
    check_password_strength,
)
from .services import get_profile, send_verification_email
from .throttling import LoginLockout, client_ip

User = get_user_model()
SESSION_BACKEND = "django.contrib.auth.backends.ModelBackend"
BAD_LOGIN = "Incorrect email or password."  # identical for unknown email, wrong password and inactive account
RESET_SENT = "If that email has an account, a reset link is on its way."
REGISTER_SENT = "Check your email. If this address can be used, we have sent you a message with the next steps."
NOCACHE = {"Cache-Control": "no-store"}


def user_data(request, user=None):
    """The logged-in user's own representation (includes the two-step status for staff)."""
    raw = getattr(request, "_request", request)  # Django's request knows the user a login has JUST set
    return UserSerializer(user or raw.user, context={"request": raw}).data


def error(field, message):
    """ValidationError that also fills "detail", which the API envelope uses as its top-level message."""
    return serializers.ValidationError({field: [message], "detail": [message]})


def is_staffish(user):
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """React calls this on start so the csrftoken cookie exists before the first POST."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request, *args, **kwargs):
        return Response({"message": "ok"})


class ProvidersView(APIView):
    """Which sign-in options exist, so the UI can hide "Continue with Google" when it is not configured."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request, *args, **kwargs):
        google = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APP", {})
        return Response({"google": bool(google.get("client_id") and google.get("secret"))})


class RegisterView(APIView):
    """Always answers the same way (202 + "check your email") whether the address is new or already registered, so the
    form cannot be used to find out who has an account. A new address gets its account and a verification email; an
    existing one gets a short "someone tried to register" notice. Nobody is logged in by registering: log in afterwards."""

    permission_classes = [AllowAny]
    throttle_scope = "register"

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        existing = User.objects.filter(email__iexact=email).first()
        if existing is not None:
            if existing.is_active:
                try:
                    send_mail(
                        f"Someone tried to sign up to {settings.SITE_NAME} with your email",
                        "Someone just tried to create an account with this email address, but you already have one.\n\n"
                        f"If it was you, you can log in or reset your password at {settings.FRONTEND_URL}/login .\n"
                        "If it was not you, you can ignore this message: nothing has changed.",
                        None,
                        [existing.email],
                    )
                except Exception:  # a mail outage must not change the answer
                    pass
        else:
            user = serializer.save()
            try:
                send_verification_email(request._request, user, signup=True)
            except Exception:  # the user can use "resend" after logging in
                pass
        return Response({"message": REGISTER_SENT}, status=status.HTTP_202_ACCEPTED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]

        lockout = LoginLockout(email, client_ip(request))
        wait = lockout.seconds_left()
        if wait:
            minutes = max(1, math.ceil(wait / 60))
            raise Throttled(wait=wait, detail=f"Too many failed login attempts. Try again in {minutes} minute(s).")

        # ModelBackend rejects inactive users and burns the same time for unknown emails.
        user = ModelBackend().authenticate(request._request, email=email, password=password)
        if user is None:
            lockout.register_failure()
            staff_account = User.objects.filter(email__iexact=email).filter(is_staff=True).first()
            if staff_account is not None:  # recorded for administrators; the client sees the same message as always
                audit.log(request, "auth.staff_login_failed", staff_account, actor=staff_account, reason="bad_credentials_or_inactive")
            raise serializers.ValidationError({"detail": [BAD_LOGIN]})

        lockout.clear()
        # login() rotates the session id; the user_logged_in signal registers the session and audits staff logins.
        login(request._request, user, backend=SESSION_BACKEND)
        return Response(user_data(request, user))


class LogoutView(APIView):
    """SessionAuthentication enforces the CSRF token here (it does for every unsafe request)."""

    permission_classes = [AllowAny]
    throttle_scope = "logout"

    def post(self, request, *args, **kwargs):
        key = request._request.session.session_key
        if key:
            UserSession.objects.filter(session_key=key).delete()
        logout(request._request)  # flushes the session: a new, empty session id is issued
        return Response({"message": "Logged out."})


class MeView(APIView):
    permission_classes = [AllowAny]

    @property
    def throttle_scope(self):
        return {"PATCH": "profile_update", "DELETE": "account_delete"}.get(self.request.method)

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(None)
        return Response(user_data(request))

    def patch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = get_profile(request.user)
        for field, value in serializer.validated_data.items():
            setattr(profile, field, value)
        profile.save()
        return Response(user_data(request))

    def delete(self, request, *args, **kwargs):
        """Delete (anonymise) my account. Needs my password, or for a Google-only account my typed email, plus a fresh
        two-step code when two-step verification is on."""
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        user = request.user
        serializer = AccountDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if user.has_usable_password():
            if not user.check_password(data.get("password", "")):
                raise error("password", "That password is not correct.")
        elif (data.get("email") or "").strip().lower() != user.email:
            raise error("email", "Type your account email address to confirm.")
        if privacy.is_last_active_superuser(user):
            raise error("detail", "This is the only active superuser account. Make someone else a superuser first.")
        mfa.require_fresh_code(user, data)
        try:
            privacy.anonymise(request._request, user)
        except ValueError:
            raise error("detail", "This is the only active superuser account. Make someone else a superuser first.")
        logout(request._request)
        return Response({"message": "Your account has been deleted."})


class MeExportView(APIView):
    """GET /auth/me/export/ : everything held about me, as JSON (the browser saves it as a file)."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "data_export"

    def get(self, request, *args, **kwargs):
        return Response(privacy.export_data(request.user), headers=NOCACHE)


class PasswordChangeView(APIView):
    """Change my password. Ends my other sessions and rotates this one. Needs a fresh two-step code when MFA is on."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "password_change"

    def post(self, request, *args, **kwargs):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        if not user.check_password(data["current_password"]):
            raise error("current_password", "That password is not correct.")
        mfa.require_fresh_code(user, data)
        check_password_strength(data["new_password"], user)
        raw = request._request
        old_key = raw.session.session_key
        user.set_password(data["new_password"])
        user.save()
        update_session_auth_hash(raw, user)  # keeps THIS browser logged in and issues a new session id
        sessions.after_key_rotation(raw, user, old_key)
        sessions.revoke_all(user, except_key=raw.session.session_key)
        if user.is_staff:
            audit.log(request, "auth.password_changed", user)
        return Response({"message": "Password updated. Your other devices have been signed out."})


class EmailVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "email_verify"

    def post(self, request, *args, **kwargs):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data["key"]
        confirmation = EmailConfirmationHMAC.from_key(key)
        if confirmation is None:
            confirmation = EmailConfirmation.objects.all_valid().filter(key=key.lower()).first()
        # confirm() returns None for an expired link (3 days) and for one that was already used.
        address = confirmation.confirm(request._request) if confirmation else None
        if address is None:
            raise serializers.ValidationError({"detail": ["This verification link is invalid or has expired."]})
        return Response({"message": "Email verified.", "email_verified": True})


class EmailResendView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "email_resend"

    def post(self, request, *args, **kwargs):
        sent = send_verification_email(request._request, request.user)
        if not sent:
            return Response({"message": "Your email is already verified."})
        return Response({"message": "Verification email sent."})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"].strip(), is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)  # valid for PASSWORD_RESET_TIMEOUT (1 hour), single use
            link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
            send_mail(
                f"Reset your {settings.SITE_NAME} password",
                f"Open this link to choose a new password (it works for one hour):\n\n{link}\n\nIf you did not ask for this, ignore this email.",
                None,
                [user.email],
            )
        # The SAME answer whether or not the account exists: no user enumeration.
        return Response({"message": RESET_SENT})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(data["uid"])), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user is None or not default_token_generator.check_token(user, data["token"]):
            raise serializers.ValidationError({"detail": ["This reset link is invalid or has expired."]})
        check_password_strength(data["password"], user)
        # Changing the password changes Django's session auth hash (so the token cannot be used twice) and logs out old sessions.
        user.set_password(data["password"])
        user.save()
        sessions.revoke_all(user)
        LoginLockout(user.email, client_ip(request)).clear()
        return Response({"message": "Password updated. You can log in now."})


# ---------------------------------------------------------------- sessions
class SessionListView(APIView):
    """My active sessions: when created, last seen, coarse device, and which one is this browser."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(sessions.listing(request.user, request._request.session.session_key), headers=NOCACHE)


class SessionRevokeAllView(APIView):
    """Sign out of ALL devices, this one included."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "password_change"  # a deliberate action; share the strict per-user limit

    def post(self, request, *args, **kwargs):
        ended = sessions.revoke_all(request.user)
        logout(request._request)
        return Response({"message": "You have been signed out of all devices.", "ended": ended})


# ---------------------------------------------------------------- two-step verification (staff)
class MfaView(APIView):
    """Base for the MFA endpoints: logged in, staff only, strict per-user throttle ("10/10min")."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [FlexibleScopedRateThrottle]
    throttle_scope = "mfa"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not is_staffish(request.user):
            raise PermissionDenied("Two-step verification is available to staff accounts.")


def _check_password(user, data):
    if user.has_usable_password() and not user.check_password(data.get("password", "")):
        raise error("password", "That password is not correct.")


class MfaStatusView(MfaView):
    def get(self, request, *args, **kwargs):
        user = request.user
        return Response(
            {**mfa.summary(request, user), "recovery_codes_left": mfa.recovery_codes_left(user) if mfa.is_enabled(user) else 0},
            headers=NOCACHE,
        )


class MfaSetupView(MfaView):
    """Start enrolment: returns the secret and an otpauth:// link (shown once; there is no QR image on purpose)."""

    def post(self, request, *args, **kwargs):
        if mfa.is_enabled(request.user):
            raise error("detail", "Two-step verification is already on. Turn it off first to set it up again.")
        secret = mfa.start_setup(request.user)
        return Response({"secret": secret, "otpauth_uri": mfa.provisioning_uri(request.user, secret)}, headers=NOCACHE)


class MfaConfirmView(MfaView):
    """Finish enrolment with the first code from the app. Returns the recovery codes: this is the only time they are shown."""

    def post(self, request, *args, **kwargs):
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            codes = mfa.confirm_setup(request.user, serializer.validated_data.get("code", ""))
            if codes is None:
                raise error("code", "That code is not correct. Check the time on your phone and try the next code.")
            mfa.mark_verified(request, request.user)  # this browser has just proven it holds the device
            audit.log(request, "mfa.enabled", request.user)
        return Response({"recovery_codes": codes, **mfa.summary(request, request.user)}, headers=NOCACHE)


class MfaVerifyView(MfaView):
    """After logging in: send a code (or a recovery code) to unlock the staff area for this session."""

    def post(self, request, *args, **kwargs):
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not mfa.is_enabled(user):
            raise error("detail", "Two-step verification is not set up for this account.")
        kind = mfa.check_any(user, serializer.validated_data)
        if kind is None:
            audit.log(request, "mfa.verify_failed", user)
            raise error("code", "That code is not correct or was already used.")
        mfa.mark_verified(request, user)
        if kind == "recovery":
            audit.log(request, "mfa.recovery_used", user, remaining=mfa.recovery_codes_left(user))
        return Response({**mfa.summary(request, user), "recovery_codes_left": mfa.recovery_codes_left(user)}, headers=NOCACHE)


class MfaDisableView(MfaView):
    """Turn two-step verification off: needs my password AND a fresh code."""

    def post(self, request, *args, **kwargs):
        serializer = SensitiveActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        if not mfa.is_enabled(user):
            raise error("detail", "Two-step verification is not on.")
        _check_password(user, data)
        with transaction.atomic():
            mfa.require_fresh_code(user, data)
            mfa.disable(user)
            mfa.clear_verified(request)
            audit.log(request, "mfa.disabled", user)
        return Response({**mfa.summary(request, user), "recovery_codes_left": 0}, headers=NOCACHE)


class MfaRecoveryCodesView(MfaView):
    """Replace all recovery codes with ten new ones (needs password and a fresh code). Shown once."""

    def post(self, request, *args, **kwargs):
        serializer = SensitiveActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        if not mfa.is_enabled(user):
            raise error("detail", "Two-step verification is not on.")
        _check_password(user, data)
        with transaction.atomic():
            mfa.require_fresh_code(user, data)
            codes = mfa.issue_recovery_codes(user)
            audit.log(request, "mfa.recovery_regenerated", user)
        return Response({"recovery_codes": codes}, headers=NOCACHE)


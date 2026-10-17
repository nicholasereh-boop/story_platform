import math

from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated, Throttled
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    EmailVerifySerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
    check_password_strength,
)
from .services import get_profile
from .throttling import LoginLockout, client_ip

User = get_user_model()
SESSION_BACKEND = "django.contrib.auth.backends.ModelBackend"
BAD_LOGIN = "Incorrect email or password."  # identical for unknown email and wrong password
RESET_SENT = "If that email has an account, a reset link is on its way."


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
    permission_classes = [AllowAny]
    throttle_scope = "register"

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request._request, user, backend=SESSION_BACKEND)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


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
            raise serializers.ValidationError({"detail": [BAD_LOGIN]})

        lockout.clear()
        login(request._request, user, backend=SESSION_BACKEND)  # also rotates the session key
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    """SessionAuthentication enforces the CSRF token here because the caller is logged in."""

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        logout(request._request)  # flushes the session
        return Response({"message": "Logged out."})


class MeView(APIView):
    permission_classes = [AllowAny]

    @property
    def throttle_scope(self):
        return "profile_update" if self.request.method == "PATCH" else None

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(None)
        return Response(UserSerializer(request.user).data)

    def patch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = get_profile(request.user)
        for field, value in serializer.validated_data.items():
            setattr(profile, field, value)
        profile.save()
        return Response(UserSerializer(request.user).data)


class EmailVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data["key"]
        confirmation = EmailConfirmationHMAC.from_key(key)
        if confirmation is None:
            confirmation = EmailConfirmation.objects.all_valid().filter(key=key.lower()).first()
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
            token = default_token_generator.make_token(user)
            link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
            send_mail(
                f"Reset your {settings.SITE_NAME} password",
                f"Open this link to choose a new password:\n\n{link}\n\nIf you did not ask for this, ignore this email.",
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
        # Changing the password changes Django's session auth hash, which logs out every old session.
        user.set_password(data["password"])
        user.save()
        LoginLockout(user.email, client_ip(request)).clear()
        return Response({"message": "Password updated. You can log in now."})

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    """Creates users that sign in with an email address (there is no username)."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email or not str(email).strip():
            raise ValueError("An email address is required.")
        user = self.model(email=str(email).strip().lower(), **extra_fields)
        user.set_password(password)  # password=None stores an unusable password (e.g. Google-only users)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length=254, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            # Belt and braces: no two emails may differ only by letter case.
            models.UniqueConstraint(Lower("email"), name="user_email_ci_unique"),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=80, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    bio = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or str(self.user)


class MFADevice(models.Model):
    """A staff member's authenticator app (TOTP). One per user. Unconfirmed until the first code is proven."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_device")
    # The shared secret, encrypted at rest (see totp.encrypt_secret). Never returned by any API after setup.
    secret_encrypted = models.CharField(max_length=300)
    confirmed_at = models.DateTimeField(null=True, blank=True)  # null = setup started but not finished: MFA is NOT on yet
    # Last accepted time step. A code is only accepted for a LATER step, so each code works once (replay protection).
    last_used_step = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MFA device of user {self.user_id} ({'on' if self.confirmed_at else 'pending'})"


class MFARecoveryCode(models.Model):
    """One single-use recovery code. Only a keyed hash is stored; the code itself is shown once."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_recovery_codes")
    code_hash = models.CharField(max_length=64)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "code_hash"], name="mfa_recovery_unique_user_hash")]


class UserSession(models.Model):
    """Registry of a user's browser sessions, so "your devices" can be listed and revoked.

    Stores only a coarse device label ("Firefox on Linux"), never an IP address or a user-agent string.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tracked_sessions")
    session_key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    device = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-last_seen_at", "-id"]

    def __str__(self):
        return f"Session of user {self.user_id}"

from allauth.socialaccount.signals import social_account_added
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile
from .services import default_display_name, fill_profile_from_google

User = get_user_model()


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Every new user gets a Profile, whichever way the account was created."""
    if created:
        Profile.objects.get_or_create(user=instance, defaults={"display_name": default_display_name(instance.email)})


@receiver(social_account_added)
def copy_google_profile(sender, request, sociallogin, **kwargs):
    """A Google account was linked: copy name and picture into blank profile fields."""
    if sociallogin.account.provider == "google":
        fill_profile_from_google(sociallogin.user, sociallogin.account.extra_data or {})


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    """Every login (password OR Google) is added to the session registry; staff logins also go to the audit log."""
    from apps.audit import service as audit

    from . import sessions

    if request is None:
        return
    sessions.register(request, user)
    if user.is_staff:
        method = "google" if str(getattr(request, "path", "")).startswith("/accounts/") else "password"
        audit.log(request, "auth.staff_login", user, actor=user, method=method)

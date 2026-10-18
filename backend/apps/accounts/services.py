"""Small account helpers shared by views, adapters and signals."""
from django.conf import settings
from django.core.mail import send_mail

from .models import Profile


def default_display_name(email):
    return (email or "").split("@")[0][:80]


def get_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user, defaults={"display_name": default_display_name(user.email)})
    return profile


def send_welcome_email(user):
    """A short welcome message to a brand-new member. Never raises: a mail outage must not break sign-up."""
    name = get_profile(user).display_name or "there"
    try:
        send_mail(
            f"Welcome to {settings.SITE_NAME}!",
            f"Hi {name},\n\n"
            f"Welcome to {settings.SITE_NAME}. Your account is ready: you can like stories and join the discussion.\n\n"
            f"Log in any time at {settings.FRONTEND_URL}/login .\n\n"
            "Whenever a new story is published we will email it to you. You can turn those emails off "
            "from your account page.\n\n"
            f"Happy reading,\nThe {settings.SITE_NAME} team",
            None,
            [user.email],
        )
        return True
    except Exception:
        return False


def fill_profile_from_google(user, extra):
    """Copy Google's name and picture, but never overwrite something the user chose themselves."""
    profile = get_profile(user)
    name = (extra.get("name") or extra.get("given_name") or "").strip()[:80]
    picture = (extra.get("picture") or "")[:500]
    changed = []
    # A display name equal to the email prefix is the automatic default, i.e. not edited by the user.
    if name and (not profile.display_name or profile.display_name == default_display_name(user.email)):
        profile.display_name = name
        changed.append("display_name")
    if picture and not profile.avatar_url:
        profile.avatar_url = picture
        changed.append("avatar_url")
    if changed:
        profile.save(update_fields=changed + ["updated_at"])

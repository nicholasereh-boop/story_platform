"""Small account helpers shared by views, adapters and signals."""
from allauth.account.models import EmailAddress

from .models import Profile


def default_display_name(email):
    return (email or "").split("@")[0][:80]


def get_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user, defaults={"display_name": default_display_name(user.email)})
    return profile


def is_email_verified(user):
    return EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists()


def send_verification_email(request, user, signup=False):
    """Create/refresh the allauth EmailAddress and email a confirmation link. Returns False if already verified."""
    address, _ = EmailAddress.objects.get_or_create(user=user, email=user.email, defaults={"primary": True, "verified": False})
    if address.verified:
        return False
    address.send_confirmation(request, signup=signup)
    return True


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

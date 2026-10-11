"""allauth hooks: send people back to the React app instead of allauth's own HTML pages."""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.http import HttpResponseRedirect

from .services import fill_profile_from_google


class AccountAdapter(DefaultAccountAdapter):
    def get_email_confirmation_url(self, request, emailconfirmation):
        # The link in the verification email opens the React page, which then calls POST /api/v1/auth/email/verify/.
        return f"{settings.FRONTEND_URL}/verify-email?key={emailconfirmation.key}"

    def is_open_for_signup(self, request):
        return True


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return True

    def save_user(self, request, sociallogin, form=None):
        """First-ever Google login: create the user, then copy name and picture to the Profile."""
        user = super().save_user(request, sociallogin, form)
        fill_profile_from_google(user, sociallogin.account.extra_data or {})
        return user

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        """Google login failed or was cancelled: back to the React login page."""
        raise ImmediateHttpResponse(HttpResponseRedirect(f"{settings.FRONTEND_URL}/login?error=google"))

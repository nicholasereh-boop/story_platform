"""Session middleware added in Phase 10. Both classes sit after AuthenticationMiddleware."""
import time

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseForbidden

from . import mfa, sessions


class SessionActivityMiddleware:
    """Idle timeout for staff and last-seen tracking.

    Staff sessions end after STAFF_SESSION_IDLE_MINUTES without a request (readers keep the normal SESSION_COOKIE_AGE).
    The time of the last request lives in the session and is refreshed at most once a minute, so this adds no database
    work to most requests. Anonymous requests are not touched at all.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = getattr(request, "session", None)
        user = getattr(request, "user", None)
        if session is not None and session.session_key and user is not None and user.is_authenticated:
            now = time.time()
            last = session.get(sessions.ACTIVITY_KEY)
            idle_limit = settings.STAFF_SESSION_IDLE_MINUTES * 60
            if (user.is_staff or user.is_superuser) and last is not None and now - last > idle_limit:
                logout(request)  # flushes the session; the request carries on as an anonymous one
                request.user = AnonymousUser()
            elif last is None or now - last >= sessions.TOUCH_EVERY_SECONDS:
                session[sessions.ACTIVITY_KEY] = now
                sessions.touch(request, user)
        return self.get_response(request)


class DjangoAdminMfaMiddleware:
    """The built-in Django admin (DJANGO_ADMIN_URL) is a second door into the same session, and it does not use the API
    permission classes. This applies the same two-step rule to it: staff with MFA must have verified this session first
    (log in on the site, enter the code, then open the admin)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        prefix = "/" + settings.DJANGO_ADMIN_URL
        user = getattr(request, "user", None)
        if request.path_info.startswith(prefix) and user is not None and user.is_authenticated:
            problem = mfa.enforcement_problem(request, user)
            if problem:
                return HttpResponseForbidden(mfa.MESSAGES[problem] + " Do this on the main site first, then reload this page.", content_type="text/plain")
        return self.get_response(request)

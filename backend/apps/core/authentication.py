"""Session authentication that also protects ANONYMOUS unsafe requests with the CSRF token.

DRF's stock SessionAuthentication only checks CSRF for logged-in users, so "login CSRF" and forged sign-up or
password-reset posts would pass. This subclass enforces the token on every unsafe request that goes through session
authentication, anonymous or not. React fetches the token once at start (GET /api/v1/auth/csrf/) and axios sends it
as X-CSRFToken. The two endpoints that must work without it (analytics collect, CSP report) set
authentication_classes = [] and only ever write anonymous data; a test lists every such exception.
"""
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import SAFE_METHODS


class StrictSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        user = getattr(request._request, "user", None)
        if not user or not user.is_active:
            if request.method not in SAFE_METHODS:
                self.enforce_csrf(request)
            return None
        self.enforce_csrf(request)
        return (user, None)

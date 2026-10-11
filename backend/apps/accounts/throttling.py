"""Failed-login lockout, keyed by (email, IP).

Only FAILED attempts count. After LOGIN_MAX_FAILURES failures inside the window the next
attempt gets HTTP 429 with a Retry-After header. A successful login clears the counter.
Unknown emails are counted exactly like known ones, so the lockout reveals nothing.
State lives in the Django cache (Redis in production).
"""
import hashlib
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle


def client_ip(request):
    """Respects REST_FRAMEWORK["NUM_PROXIES"] (set it when running behind Nginx)."""
    return BaseThrottle().get_ident(request)


class LoginLockout:
    def __init__(self, email, ip):
        digest = hashlib.sha256(f"{email.lower()}|{ip}".encode()).hexdigest()
        self.key = f"login-failures:{digest}"
        self.window = settings.LOGIN_FAILURE_WINDOW_SECONDS
        self.limit = settings.LOGIN_MAX_FAILURES

    def seconds_left(self):
        """0 if the login may proceed, otherwise how long until it may."""
        state = cache.get(self.key)
        if not state or state["count"] < self.limit:
            return 0
        return max(1, int(state["first"] + self.window - time.time()))

    def register_failure(self):
        now = time.time()
        state = cache.get(self.key) or {"count": 0, "first": now}
        state["count"] += 1
        cache.set(self.key, state, timeout=max(1, int(state["first"] + self.window - now)))

    def clear(self):
        cache.delete(self.key)

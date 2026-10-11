import re

from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle


class AdminWriteThrottle(UserRateThrottle):
    """Limits WRITES by logged-in staff (default 300/min per staff user, THROTTLE_ADMIN_WRITE). Reads, anonymous
    requests and readers are not affected. A compromised or runaway staff session cannot bulk-edit at machine speed."""

    scope = "admin_write"

    def allow_request(self, request, view):
        user = getattr(request, "user", None)
        if request.method in SAFE_METHODS or not (user and user.is_authenticated and user.is_staff):
            return True
        return super().allow_request(request, view)


_UNITS = {"s": 1, "sec": 1, "second": 1, "m": 60, "min": 60, "minute": 60, "h": 3600, "hour": 3600, "d": 86400, "day": 86400}


class FlexibleScopedRateThrottle(ScopedRateThrottle):
    """ScopedRateThrottle that understands rates with a multiple, such as "10/10min" (10 requests per 10 minutes).
    Stock DRF reads only the first letter of the period, so "10/10min" would silently mean "10 per minute"."""

    def parse_rate(self, rate):
        if rate is None:
            return (None, None)
        match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d*)\s*([a-z]+)\s*", str(rate).lower())
        if not match or match.group(3) not in _UNITS:
            return super().parse_rate(rate)
        count, multiple, unit = match.groups()
        return int(count), int(multiple or 1) * _UNITS[unit]

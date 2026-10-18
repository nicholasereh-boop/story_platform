"""POST /api/v1/analytics/collect/ : the only public analytics endpoint.

It ALWAYS answers 204 with an empty body (except when throttled), whether the event was counted or ignored, so a caller
learns nothing about why. No cookies, no login, no CSRF (it only ever writes anonymous, hashed data).
"""
import hashlib
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.counters import adjust_story_counter
from apps.stories.models import Story

from . import tracking
from .models import PageViewEvent, Visitor


def _ignored():
    return Response(status=204)


def _payload(request):
    try:
        data = request.data
    except APIException:  # unparseable JSON or an unsupported content type: ignore the event
        return {}
    return data if isinstance(data, dict) else {}


def _opted_out(request):
    """Do Not Track / Global Privacy Control headers (the browser also checks them before sending)."""
    return request.META.get("HTTP_DNT") == "1" or request.META.get("HTTP_SEC_GPC") == "1"


def _is_staff(user):
    """Logged-in staff are never counted. `user` is the lazy session user captured in initialize_request()."""
    return bool(user is not None and user.is_authenticated and user.is_staff)


def _first_seen(visitor_hash, path, now):
    """True if this visitor has NOT viewed this path within the dedupe window (so the view should be counted).

    The check is a cache `add` (atomic: only one of two simultaneous requests wins). If the cache is down it falls
    back to one indexed database query.
    """
    window = timedelta(minutes=settings.ANALYTICS_DEDUPE_MINUTES)
    try:
        path_key = hashlib.sha1(path.encode()).hexdigest()[:16]  # stable across processes (unlike hash())
        return cache.add(f"analytics:seen:{visitor_hash[:32]}:{path_key}", 1, int(window.total_seconds()))
    except Exception:  # Redis unreachable: do not lose analytics, just use the database
        return not PageViewEvent.objects.filter(
            visitor__visitor_key_hash=visitor_hash, path=path, created_at__gte=now - window
        ).exists()


def _touch_visitor(visitor_hash, now):
    visitor, created = Visitor.objects.get_or_create(
        visitor_key_hash=visitor_hash, defaults={"first_seen_at": now, "last_seen_at": now}
    )
    if not created:
        Visitor.objects.filter(pk=visitor.pk).update(last_seen_at=now)
    return visitor


class CollectView(APIView):
    authentication_classes = []  # anonymous by design; also means no CSRF check
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "analytics"  # 120/min per IP, THROTTLE_ANALYTICS
    http_method_names = ["post", "options"]

    def initialize_request(self, request, *args, **kwargs):
        # This view has no DRF authenticators, so DRF replaces request.user with AnonymousUser as soon as the
        # throttle looks at it. Keep Django's lazy session user from before that, so logged-in staff can be recognised
        # (without DRF session authentication, which would demand a CSRF token for logged-in visitors).
        self.session_user = getattr(request, "user", None)
        return super().initialize_request(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not settings.ANALYTICS_ENABLED or _opted_out(request) or _is_staff(self.session_user):
            return _ignored()
        data = _payload(request)
        # Consent mode "opt_in" (Phase 10): nothing is counted unless the browser says the visitor explicitly accepted.
        if settings.PRIVACY_CONSENT_MODE == "opt_in" and data.get("consent") is not True:
            return _ignored()
        parsed = tracking.classify_path(data.get("path"))
        visitor_id, session_id = data.get("visitor_id"), data.get("session_id")
        if parsed is None or not tracking.valid_id(visitor_id) or not tracking.valid_id(session_id):
            return _ignored()
        agent = request.META.get("HTTP_USER_AGENT", "")
        if tracking.is_bot(agent):
            return _ignored()
        path, slug = parsed

        story_id = None
        if slug:
            story_id = Story.objects.public().filter(slug=slug).values_list("id", flat=True).first()
            if story_id is None:
                return _ignored()  # not public (draft, scheduled, archived, unknown): not counted at all

        now = timezone.now()
        visitor_hash = tracking.hash_id(visitor_id, "visitor")
        if not _first_seen(visitor_hash, path, now):
            return _ignored()  # a refresh or repeat view inside the window

        own_hosts = [urlparse(settings.FRONTEND_URL).hostname, request.get_host().split(":")[0]]
        try:
            with transaction.atomic():
                visitor = _touch_visitor(visitor_hash, now)
                PageViewEvent.objects.create(
                    visitor=visitor,
                    story_id=story_id,
                    path=path,
                    session_key_hash=tracking.hash_id(session_id, "session"),
                    referrer_domain=tracking.referrer_domain(data.get("referrer"), own_hosts),
                    user_agent_category=tracking.device_category(agent),
                    created_at=now,
                )
                if story_id:
                    adjust_story_counter(story_id, "view_count", +1)  # atomic; only for a COUNTED story view
        except IntegrityError:
            pass  # a simultaneous first visit by the same browser: the other request created the Visitor
        return _ignored()

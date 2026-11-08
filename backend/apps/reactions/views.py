import re
import secrets

from django.utils.cache import patch_cache_control
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.authentication import StrictSessionAuthentication
from apps.core.http import mark_per_user
from apps.stories.public_views import get_public_story_or_404

from .services import has_liked, like_as_visitor, like_story, unlike_as_visitor, unlike_story

# The anonymous visitor's identity lives INSIDE the session (server side). It rides on the `sessionid` cookie that the
# privacy page already lists, so liking adds no new cookie. Logging in keeps the session data (the key rotates, the data
# stays), so a browser that liked a story as a visitor can still be recognised after it logs in.
SESSION_KEY = "like_visitor"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")


def visitor_id_for(request, create=False):
    """This browser's visitor token, or None. `create=True` makes one (and so starts a session) for a first-time liker."""
    token = request.session.get(SESSION_KEY)
    if isinstance(token, str) and TOKEN_RE.match(token):
        return token
    if not create:
        return None
    token = secrets.token_urlsafe(32)  # 43 URL-safe characters
    request.session[SESSION_KEY] = token
    return token


def like_state(request, story):
    """{count, liked}: the stored counter plus whether THIS reader or browser has liked it."""
    user = request.user if request.user.is_authenticated else None
    return {"count": story.like_count, "liked": has_liked(user, visitor_id_for(request), story)}


class StoryLikeView(APIView):
    """POST likes, DELETE unlikes. Open to everyone: a logged-in reader is identified by account, a visitor by the
    token kept in their session. Both are idempotent and answer {count, liked}. (Commenting stays login-only.)"""

    authentication_classes = [StrictSessionAuthentication]  # CSRF is enforced for visitors too
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    http_method_names = ["post", "delete", "options"]

    def get_throttles(self):
        self.throttle_scope = "like" if self.request.user.is_authenticated else "like_anonymous"
        return super().get_throttles()

    def post(self, request, slug, **kwargs):
        story = get_public_story_or_404(slug)  # 404 first, so a non-public story never starts a session
        if request.user.is_authenticated:
            like_story(request.user, story, visitor_id=visitor_id_for(request))
        else:
            like_as_visitor(visitor_id_for(request, create=True), story)
        story.refresh_from_db(fields=["like_count"])
        return Response({"count": story.like_count, "liked": True})

    def delete(self, request, slug, **kwargs):
        story = get_public_story_or_404(slug)
        if request.user.is_authenticated:
            unlike_story(request.user, story, visitor_id=visitor_id_for(request))
        else:
            visitor = visitor_id_for(request)
            if visitor:
                unlike_as_visitor(visitor, story)
        story.refresh_from_db(fields=["like_count"])
        return Response({"count": story.like_count, "liked": False})


class StoryLikesView(APIView):
    """GET {count, liked}. Anyone may read; `liked` says whether this reader or browser already liked the story."""

    authentication_classes = [StrictSessionAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_read"
    http_method_names = ["get", "head", "options"]

    def get(self, request, slug, **kwargs):
        story = get_public_story_or_404(slug)
        response = mark_per_user(Response(like_state(request, story)), request)
        if visitor_id_for(request):
            patch_cache_control(response, private=True)  # the answer depends on this browser: never share it through a cache
        return response
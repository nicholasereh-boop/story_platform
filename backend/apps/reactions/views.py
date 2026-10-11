from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.http import mark_per_user
from apps.stories.public_views import get_public_story_or_404

from .models import Like
from .services import like_story, unlike_story


def like_state(user, story):
    """{count, liked}: the stored counter plus whether THIS reader has liked it (always false for visitors)."""
    liked = bool(user and user.is_authenticated and Like.objects.filter(user=user, story=story).exists())
    return {"count": story.like_count, "liked": liked}


class StoryLikeView(APIView):
    """POST = like, DELETE = unlike. Both are idempotent and always answer 200 with the new {count, liked}."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "like"  # 60/min per user, THROTTLE_LIKE
    http_method_names = ["post", "delete", "options"]

    def post(self, request, slug):
        story = get_public_story_or_404(slug)
        like_story(request.user, story)
        story.refresh_from_db(fields=["like_count"])
        return Response({"count": story.like_count, "liked": True})

    def delete(self, request, slug):
        story = get_public_story_or_404(slug)
        unlike_story(request.user, story)
        story.refresh_from_db(fields=["like_count"])
        return Response({"count": story.like_count, "liked": False})


class StoryLikesView(APIView):
    """GET {count, liked}. Anyone may read; `liked` is false for visitors."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_read"
    http_method_names = ["get", "head", "options"]

    def get(self, request, slug):
        story = get_public_story_or_404(slug)
        response = Response(like_state(request.user, story))
        return mark_per_user(response, request)

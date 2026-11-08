from django.conf import settings
from django.http import Http404
from rest_framework.permissions import BasePermission


class NewsEnabled(BasePermission):
    """NEWS_ENABLED=false switches the whole News section off: every endpoint answers 404, like a page that does not exist."""

    def has_permission(self, request, view):
        if not settings.NEWS_ENABLED:
            raise Http404()
        return True


class NewsPublicEnabled(BasePermission):
    """NEWS_PUBLIC_ENABLED=false keeps News staff-only (staging a rollout) while the public endpoints answer 404."""

    def has_permission(self, request, view):
        if not (settings.NEWS_ENABLED and settings.NEWS_PUBLIC_ENABLED):
            raise Http404()
        return True


class NewsCommentsEnabled(BasePermission):
    """NEWS_COMMENTS_ENABLED=false: the comment endpoints answer 404, as if comments did not exist."""

    def has_permission(self, request, view):
        if not settings.NEWS_COMMENTS_ENABLED:
            raise Http404()
        return True

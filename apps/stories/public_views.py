"""READ-ONLY public API: what a visitor may see. No login, GET only.

Every query starts from Story.objects.public() (published AND published_at already passed), so drafts, scheduled,
archived and future-dated stories can never appear in a list, a search, a related list, a count or a detail response.
A non-public story is a plain 404 (never 403), so its existence is not revealed.
"""
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.http import mark_per_user

from .models import Category, Story, Tag
from .public_serializers import (
    PublicCategorySerializer,
    PublicStoryListSerializer,
    PublicStorySerializer,
    PublicTagSerializer,
)
from .services import publish_due

SITEMAP_LIMIT = 5000
SITEMAP_CACHE_KEY = "public:sitemap-data"
SITEMAP_CACHE_SECONDS = 300
RELATED_LIMIT = 4
SEARCH_MIN, SEARCH_MAX = 2, 100


class PublicReadMixin:
    """Shared rules for every public view."""

    authentication_classes = []  # anonymous by design: responses never depend on who asks, and no CSRF involved
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]  # replaces the default 100/hour anonymous limit
    throttle_scope = "public_read"  # 120/min per IP, see THROTTLE_PUBLIC_READ
    http_method_names = ["get", "head", "options"]


def public_stories():
    """Public stories with everything a card needs loaded in a FIXED number of queries (no N+1)."""
    publish_due()  # scheduled stories that became due appear without waiting for Celery
    return (
        Story.objects.public()
        .select_related("created_by__profile", "cover_image")
        .prefetch_related("categories", "tags")
        .defer("content_json")  # lists never need the document itself
        .order_by("-published_at", "-id")
    )


def get_public_story_or_404(slug):
    """The PUBLIC story with this slug, or a plain 404 (drafts, scheduled, archived and future stories do not exist)."""
    publish_due()
    return get_object_or_404(Story.objects.public(), slug=slug)


def public_story_filter(prefix):
    """Q matching public stories through a relation, e.g. prefix="stories" for Category.stories."""
    return Q(**{f"{prefix}__status": Story.Status.PUBLISHED, f"{prefix}__published_at__lte": timezone.now()})


# ---------------------------------------------------------------- stories
class PublicStoryListView(PublicReadMixin, generics.ListAPIView):
    serializer_class = PublicStoryListSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = public_stories()
        if params.get("category"):
            qs = qs.filter(categories__slug=params["category"])
        if params.get("tag"):
            qs = qs.filter(tags__slug=params["tag"])
        if params.get("featured") in ("1", "true"):
            qs = qs.filter(is_featured=True)
        return qs


class PublicStoryDetailView(PublicReadMixin, generics.RetrieveAPIView):
    serializer_class = PublicStorySerializer
    lookup_field = "slug"
    # Unlike the other public views, the detail page recognises a logged-in reader (for `liked_by_me`).
    # Reading is a safe method, so session auth adds no CSRF requirement.
    authentication_classes = [SessionAuthentication]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == 200:
            mark_per_user(response, request)  # body differs per reader: Vary: Cookie (+ private when logged in)
        return response

    def get_queryset(self):
        publish_due()
        return (
            Story.objects.public()
            .select_related("created_by__profile", "cover_image")
            .prefetch_related("categories", "tags")
        )


class PublicRelatedStoriesView(PublicReadMixin, generics.ListAPIView):
    """Up to 4 public stories sharing categories/tags with this one, most shared terms first, then newest."""

    serializer_class = PublicStoryListSerializer
    pagination_class = None

    def get_queryset(self):
        story = get_object_or_404(Story.objects.public(), slug=self.kwargs["slug"])
        category_ids = list(story.categories.values_list("id", flat=True))
        tag_ids = list(story.tags.values_list("id", flat=True))
        if not category_ids and not tag_ids:
            return Story.objects.none()
        shared = Count("categories", filter=Q(categories__in=category_ids), distinct=True) + Count(
            "tags", filter=Q(tags__in=tag_ids), distinct=True
        )
        return (
            public_stories()
            .exclude(pk=story.pk)
            .filter(Q(categories__in=category_ids) | Q(tags__in=tag_ids))
            .annotate(shared_terms=shared)
            .order_by("-shared_terms", "-published_at", "-id")[:RELATED_LIMIT]
        )


# ---------------------------------------------------------------- categories & tags
class PublicCategoryListView(PublicReadMixin, generics.ListAPIView):
    """Only categories with at least one PUBLIC story; story_count counts public stories only."""

    serializer_class = PublicCategorySerializer
    pagination_class = None

    def get_queryset(self):
        publish_due()
        count = Count("stories", filter=public_story_filter("stories"), distinct=True)
        return Category.objects.annotate(story_count=count).filter(story_count__gt=0).order_by("name")


class PublicCategoryStoriesView(PublicReadMixin, generics.ListAPIView):
    serializer_class = PublicStoryListSerializer

    def get_queryset(self):
        publish_due()
        category = get_object_or_404(Category, slug=self.kwargs["slug"])
        qs = public_stories().filter(categories=category)
        if not qs.exists():
            raise Http404  # a category with no public stories does not exist for visitors
        return qs


class PublicTagListView(PublicReadMixin, generics.ListAPIView):
    serializer_class = PublicTagSerializer
    pagination_class = None

    def get_queryset(self):
        publish_due()
        count = Count("stories", filter=public_story_filter("stories"), distinct=True)
        return Tag.objects.annotate(story_count=count).filter(story_count__gt=0).order_by("name")


# ---------------------------------------------------------------- search
class PublicSearchView(PublicReadMixin, generics.ListAPIView):
    """?q= matches title, excerpt and the plain-text copy of the story (case-insensitive)."""

    serializer_class = PublicStoryListSerializer

    def get_queryset(self):
        q = (self.request.query_params.get("q") or "").strip()
        if not (SEARCH_MIN <= len(q) <= SEARCH_MAX):
            message = f"Search must be {SEARCH_MIN} to {SEARCH_MAX} characters."
            raise serializers.ValidationError({"q": [message], "detail": [message]})  # "detail" becomes the top-level message
        match = Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(search_text__icontains=q)
        return public_stories().filter(match)


# ---------------------------------------------------------------- sitemap data
class PublicSitemapDataView(PublicReadMixin, APIView):
    """[{slug, updated_at}] of public stories, cached 5 minutes. Feeds a sitemap.xml generator later."""

    def get(self, request, *args, **kwargs):
        data = cache.get(SITEMAP_CACHE_KEY)
        if data is None:
            publish_due()
            rows = Story.objects.public().order_by("-published_at", "-id").values("slug", "updated_at")[:SITEMAP_LIMIT]
            data = [{"slug": r["slug"], "updated_at": r["updated_at"].isoformat()} for r in rows]
            cache.set(SITEMAP_CACHE_KEY, data, SITEMAP_CACHE_SECONDS)
        return Response(data)

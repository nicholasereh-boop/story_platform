"""READ-ONLY public news API: anonymous, GET only, no cookies or CSRF. Every query starts from NewsArticle.objects.public(), so drafts,
pending, scheduled, withdrawn and quarantined articles, and articles whose licence has lapsed, can never appear anywhere. A hidden article is a plain 404.
Lists are cached in Redis; the key contains a version number that every editorial change bumps, so a change shows up immediately."""
import hashlib
from datetime import date

from django.core.cache import cache
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination

from .models import NewsArticle, NewsCategory, NewsSource, NewsViewCount
from .permissions import NewsPublicEnabled
from .serializers_articles import category_data, public_card, public_detail
from .services import articles, rights

SEARCH_MIN, SEARCH_MAX = 2, 100
RELATED_LIMIT = 4
HOME_LIMIT = 6


class SearchThrottle(SimpleRateThrottle):
    """A tighter per-IP limit that applies only to requests that actually search (?q=...)."""

    scope = "news_search"

    def get_cache_key(self, request, view):
        if not (request.query_params.get("q") or "").strip():
            return None
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class PublicNewsView(APIView):
    authentication_classes = []
    permission_classes = [NewsPublicEnabled, AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_read"
    http_method_names = ["get", "head", "options"]


def public_articles():
    """Public articles with everything a card needs in a fixed number of queries."""
    articles.publish_due()  # scheduled articles that became due appear without waiting for Celery
    return NewsArticle.objects.public().select_related("source", "category").prefetch_related("assets__image").defer("body")


def _cached(kind, request, build):
    """Cache `build()` per query string and cache version. Cache trouble never breaks the page."""
    raw = request.META.get("QUERY_STRING", "")
    key = f"news:{kind}:{articles.cache_version()}:{hashlib.sha1(raw.encode()).hexdigest()}"
    try:
        hit = cache.get(key)
    except Exception:
        hit = None
    if hit is not None:
        return Response(hit)
    response = build()
    try:
        cache.set(key, response.data, settings.NEWS_PUBLIC_CACHE_SECONDS)
    except Exception:
        pass
    return response


def apply_filters(qs, params):
    category = (params.get("category") or "").strip()
    if category:
        qs = qs.filter(category__slug=category)
    source = (params.get("source") or "").strip()
    if source:
        qs = qs.filter(source__slug=source)
    if params.get("featured") in ("1", "true"):
        qs = qs.filter(is_featured=True)
    if params.get("breaking") in ("1", "true"):
        qs = qs.filter(is_breaking=True)
    after, before = parse_date(params.get("from") or ""), parse_date(params.get("to") or "")
    if after:
        qs = qs.filter(published_at__date__gte=after)
    if before:
        qs = qs.filter(published_at__date__lte=before)
    q = (params.get("q") or "").strip()
    if q and SEARCH_MIN <= len(q) <= SEARCH_MAX:
        qs = qs.filter(Q(title__icontains=q) | Q(standfirst__icontains=q) | Q(body__icontains=q))
    elif q:
        qs = qs.none()
    return qs


class ArticleListView(PublicNewsView):
    throttle_classes = [ScopedRateThrottle, SearchThrottle]

    def get(self, request, **kwargs):
        def build():
            qs = apply_filters(public_articles(), request.query_params).order_by("-published_at", "-id")
            paginator = StandardPagination()
            page = paginator.paginate_queryset(qs, request, view=self)
            return paginator.get_paginated_response([public_card(a) for a in page])

        return _cached("list", request, build)


def get_public_article_or_404(slug):
    """The article a reader may see, or a 404. Rights are re-checked at read time with the record the article was published under:
    a lapsed licence is a 404, not a stale page. Returns (article, rights decision)."""
    article = get_object_or_404(public_articles().defer(None), slug=slug)
    decision = rights.evaluate(article.source, record=article.rights_record)
    ok, _ = articles.check_publishable(article)
    if not (decision.allowed and ok):
        raise Http404()
    return article, decision


class ArticleDetailView(PublicNewsView):
    def get(self, request, slug, **kwargs):
        article, decision = get_public_article_or_404(slug)
        return Response(public_detail(article, decision))


class CategoryListView(PublicNewsView):
    def get(self, request, **kwargs):
        def build():
            return Response([category_data(c) for c in NewsCategory.objects.filter(is_active=True)])

        return _cached("categories", request, build)


class FeaturedView(PublicNewsView):
    def get(self, request, **kwargs):
        def build():
            return Response([public_card(a) for a in public_articles().filter(is_featured=True).order_by("-published_at", "-id")[:HOME_LIMIT]])

        return _cached("featured", request, build)


class BreakingView(PublicNewsView):
    def get(self, request, **kwargs):
        def build():
            return Response([public_card(a) for a in public_articles().filter(is_breaking=True).order_by("-published_at", "-id")[:HOME_LIMIT]])

        return _cached("breaking", request, build)


class RelatedView(PublicNewsView):
    def get(self, request, slug, **kwargs):
        article = get_object_or_404(public_articles(), slug=slug)
        qs = public_articles().exclude(pk=article.pk)
        if article.category_id:
            same = list(qs.filter(category_id=article.category_id).order_by("-published_at", "-id")[:RELATED_LIMIT])
        else:
            same = []
        if len(same) < RELATED_LIMIT:
            have = [a.pk for a in same]
            same += list(qs.exclude(pk__in=have).order_by("-published_at", "-id")[: RELATED_LIMIT - len(same)])
        return Response([public_card(a) for a in same])


class SourceListView(PublicNewsView):
    """Public fields only: who we publish from. Never terms evidence, contacts, quotas or approval notes."""

    def get(self, request, **kwargs):
        qs = NewsSource.objects.filter(approval_state=NewsSource.Approval.APPROVED, is_active=True)
        return Response([{"name": s.name, "slug": s.slug, "website_url": s.website_url, "source_type": s.source_type} for s in qs])


class ArticleViewCounterView(APIView):
    """POST /news/articles/<slug>/view/ : the page-view counter some licences require. Counts per day; stores nothing about the visitor."""

    authentication_classes = []
    permission_classes = [NewsPublicEnabled, AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "news_counter"
    http_method_names = ["post", "options"]

    def post(self, request, slug, **kwargs):
        article = get_object_or_404(NewsArticle.objects.public().select_related("rights_record"), slug=slug)
        if not (article.rights_record and article.rights_record.requires_counter):
            return Response({"counted": False})
        today = timezone.localdate()
        with transaction.atomic():
            updated = NewsViewCount.objects.filter(article=article, day=today).update(count=F("count") + 1)
            if not updated:
                try:
                    with transaction.atomic():
                        NewsViewCount.objects.create(article=article, day=today, count=1)
                except IntegrityError:
                    NewsViewCount.objects.filter(article=article, day=today).update(count=F("count") + 1)
        return Response({"counted": True})


__all__ = ["date"]

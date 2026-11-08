"""Staff newsroom API: categories, articles, the editorial actions, assets and revision history. All staff-only (is_staff checked on the server).
Editorial actions call services/articles.py, where the rights gate lives; a view can never publish around it."""
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit import service as audit
from apps.core.pagination import StandardPagination

from .models import NewsArticle, NewsAsset, NewsCategory
from .serializers_articles import (
    ArticleUpdateSerializer, ArticleWriteSerializer, AssetWriteSerializer, CategoryWriteSerializer, article_admin_data,
    asset_admin_data, category_data, revision_data,
)
from .services import articles
from .services.articles import ArticleError
from .views import StaffView, _rights_failure  # noqa: F401


def _fail(exc):
    return ValidationError({"detail": str(exc), "blockers": getattr(exc, "reasons", [])})


class AdminCategoryListCreateView(StaffView):
    def get(self, request, **kwargs):
        qs = NewsCategory.objects.annotate(article_total=Count("articles"))
        return Response([{**category_data(c), "article_total": c.article_total} for c in qs])

    def post(self, request, **kwargs):
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            category = serializer.save()
            audit.log(request, "news.category_create", category, name=category.name)
            articles.bump_cache()
        return Response(category_data(category), status=201)


class AdminCategoryDetailView(StaffView):
    def patch(self, request, pk, **kwargs):
        category = get_object_or_404(NewsCategory, pk=pk)
        serializer = CategoryWriteSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            category = serializer.save()
            audit.log(request, "news.category_update", category, name=category.name)
            articles.bump_cache()
        return Response(category_data(category))

    def delete(self, request, pk, **kwargs):
        category = get_object_or_404(NewsCategory, pk=pk)
        with transaction.atomic():
            audit.log(request, "news.category_delete", category, name=category.name)
            category.delete()  # articles keep existing: their category becomes empty
            articles.bump_cache()
        return Response(status=204)


class AdminArticleListCreateView(StaffView):
    def get(self, request, **kwargs):
        qs = NewsArticle.objects.select_related("source", "category").order_by("-updated_at", "-id")
        status_ = request.query_params.get("status")
        if status_ in NewsArticle.Status.values:
            qs = qs.filter(status=status_)
        if request.query_params.get("source"):
            qs = qs.filter(source_id=request.query_params["source"]) if request.query_params["source"].isdigit() else qs
        if request.query_params.get("imported") in ("1", "true"):
            qs = qs.filter(imported=True)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(slug__icontains=q))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([article_admin_data(a) for a in page])

    def post(self, request, **kwargs):
        serializer = ArticleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        source = data.pop("source", None)
        if source is None:
            raise ValidationError({"source": "Choose the source this article belongs to (use the ResourceBoard source for original reporting)."})
        data.pop("note", None)
        try:
            with transaction.atomic():
                article = articles.create_article(request.user, source, data)
                audit.log(request, "news.article_create", article, title=article.title, source=source.name)
        except ArticleError as exc:
            raise _fail(exc)
        return Response(article_admin_data(article, full=True), status=201)


class AdminArticleDetailView(StaffView):
    def get(self, request, pk, **kwargs):
        article = get_object_or_404(NewsArticle.objects.select_related("source", "category", "rights_record").prefetch_related("assets__image"), pk=pk)
        return Response(article_admin_data(article, full=True))

    def patch(self, request, pk, **kwargs):
        article = get_object_or_404(NewsArticle.objects.select_related("source", "category", "rights_record"), pk=pk)
        serializer = ArticleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("source", None)  # an article never moves to another source: its rights are tied to the one it came from
        note = data.pop("note", "")
        try:
            with transaction.atomic():
                article = articles.update_article(article, request.user, data, note)
                audit.log(request, "news.article_update", article, title=article.title, fields=sorted(data))
        except ArticleError as exc:
            raise _fail(exc)
        return Response(article_admin_data(article, full=True))


class AdminArticleActionView(StaffView):
    """POST submit | publish | schedule | reject | withdraw | restore."""

    def post(self, request, pk, action, **kwargs):
        article = get_object_or_404(NewsArticle.objects.select_related("source", "category", "rights_record"), pk=pk)
        try:
            with transaction.atomic():
                if action == "submit":
                    articles.submit(article, request.user)
                    audit.log(request, "news.article_submit", article, title=article.title)
                elif action == "publish":
                    articles.publish(article, request.user)
                    audit.log(request, "news.article_publish", article, title=article.title, source=article.source.name)
                elif action == "schedule":
                    when = parse_datetime(str(request.data.get("scheduled_for") or ""))
                    if when is None:
                        raise ArticleError("Choose a valid date and time.")
                    articles.publish(article, request.user, when=when)
                    audit.log(request, "news.article_schedule", article, title=article.title, when=when)
                elif action == "reject":
                    articles.reject(article, request.user, request.data.get("reason"))
                    audit.log(request, "news.article_reject", article, title=article.title, reason=article.review_note)
                elif action == "withdraw":
                    articles.withdraw(article, request.user, request.data.get("reason"))
                    audit.log(request, "news.article_withdraw", article, title=article.title, reason=article.review_note)
                elif action == "restore":
                    articles.restore(article, request.user)
                    audit.log(request, "news.article_restore", article, title=article.title)
                else:
                    raise ArticleError("Unknown action.")
        except ArticleError as exc:
            raise _fail(exc)
        return Response(article_admin_data(article, full=True))


class AdminArticleRevisionsView(StaffView):
    def get(self, request, pk, **kwargs):
        article = get_object_or_404(NewsArticle, pk=pk)
        return Response([revision_data(r) for r in article.revisions.select_related("user")[:100]])


class AdminAssetListCreateView(StaffView):
    def get(self, request, pk, **kwargs):
        article = get_object_or_404(NewsArticle, pk=pk)
        return Response([asset_admin_data(a) for a in article.assets.select_related("image")])

    def post(self, request, pk, **kwargs):
        article = get_object_or_404(NewsArticle, pk=pk)
        serializer = AssetWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            asset = serializer.save(article=article)
            audit.log(request, "news.asset_create", asset, article=article.title, kind=asset.kind)
            articles.bump_cache()
        return Response(asset_admin_data(asset), status=201)


class AdminAssetDetailView(StaffView):
    def patch(self, request, pk, **kwargs):
        asset = get_object_or_404(NewsAsset.objects.select_related("image"), pk=pk)
        serializer = AssetWriteSerializer(asset, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            asset = serializer.save(approval_state=NewsAsset.Approval.PENDING)  # any change needs clearing again
            audit.log(request, "news.asset_update", asset, article=asset.article.title)
            articles.bump_cache()
        return Response(asset_admin_data(asset))

    def delete(self, request, pk, **kwargs):
        asset = get_object_or_404(NewsAsset, pk=pk)
        with transaction.atomic():
            audit.log(request, "news.asset_update", asset, article=asset.article.title, removed=True)
            asset.delete()
            articles.bump_cache()
        return Response(status=204)


class AdminAssetActionView(StaffView):
    """POST clear | reject. Clearing needs a creator or credit, a licence, and evidence; clearing something that cannot be shown commercially is allowed but it stays hidden."""

    def post(self, request, pk, action, **kwargs):
        from django.utils import timezone

        asset = get_object_or_404(NewsAsset.objects.select_related("image", "article"), pk=pk)
        with transaction.atomic():
            if action == "clear":
                missing = [n for n, v in (("credit", asset.credit or asset.creator), ("licence", asset.licence), ("evidence", asset.evidence_url)) if not v]
                if missing:
                    raise ValidationError({"detail": "Before clearing, fill in: " + ", ".join(missing) + "."})
                asset.approval_state = NewsAsset.Approval.CLEARED
                audit.log(request, "news.asset_clear", asset, article=asset.article.title, licence=asset.licence)
            elif action == "reject":
                asset.approval_state = NewsAsset.Approval.REJECTED
                audit.log(request, "news.asset_reject", asset, article=asset.article.title)
            else:
                raise ValidationError({"detail": "Unknown action."})
            asset.reviewed_by = request.user
            asset.reviewed_at = timezone.now()
            asset.save(update_fields=["approval_state", "reviewed_by", "reviewed_at"])
            articles.bump_cache()
        return Response(asset_admin_data(asset))

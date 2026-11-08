"""Staff endpoints for importing and ingestion health."""
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit import service as audit
from apps.core.pagination import StandardPagination

from .models import NewsIngestionRun, NewsSource
from .serializers_articles import ArticleWriteSerializer, article_admin_data
from .services import ingest
from .services.articles import ArticleError
from .views import StaffView


class ImportSerializer(ArticleWriteSerializer):
    source = serializers.PrimaryKeyRelatedField(queryset=NewsSource.objects.all())  # required here


def run_data(r):
    return {"id": r.pk, "source": r.source_id, "source_name": r.source.name, "status": r.status, "reason": r.reason, "message": r.message, "http_status": r.http_status,
            "fetched": r.fetched, "created": r.created, "duplicates": r.duplicates, "updated": r.updated, "changed_live": r.changed_live, "errors": r.errors,
            "started_at": r.started_at, "finished_at": r.finished_at}


class AdminImportPreviewView(StaffView):
    """POST: what would importing this article do? Nothing is saved."""

    def post(self, request, **kwargs):
        serializer = ImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        source = data.pop("source")
        data.pop("note", None)
        return Response(ingest.preview_import(source, data))


class AdminImportView(StaffView):
    """POST: import one article by hand into the review queue (duplicates are refused)."""

    def post(self, request, **kwargs):
        serializer = ImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        source = data.pop("source")
        data.pop("note", None)
        try:
            with transaction.atomic():
                article = ingest.import_manual(request.user, source, data)
                audit.log(request, "news.article_import", article, title=article.title, source=source.name)
        except ArticleError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(article_admin_data(article, full=True), status=201)


class AdminSourcePollView(StaffView):
    """POST: poll this source now. The same quota, rights and safety checks apply as for the scheduled poll; only the interval wait is skipped."""

    def post(self, request, pk, **kwargs):
        source = get_object_or_404(NewsSource, pk=pk)
        run = ingest.run_source(source, force=True)
        run.source = source
        return Response(run_data(run))


class AdminIngestionView(StaffView):
    """GET: recent runs, newest first (filter ?source=<id>)."""

    def get(self, request, **kwargs):
        qs = NewsIngestionRun.objects.select_related("source")
        if (request.query_params.get("source") or "").isdigit():
            qs = qs.filter(source_id=request.query_params["source"])
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([run_data(r) for r in page])


class AdminIngestionHealthView(StaffView):
    """GET: one health line per source that has an adapter (last result, failure streak, today's use of the quota, why it would be skipped now)."""

    def get(self, request, **kwargs):
        return Response([{"source": s.pk, "name": s.name, "adapter": s.adapter, **ingest.health(s)} for s in NewsSource.objects.exclude(adapter="")])

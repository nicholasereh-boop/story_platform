"""Staff endpoints for news sources and rights (/api/v1/news/admin/...). Each checks is_staff on the server; the React
pages are only a convenience. Handlers accept **kwargs because the API is URL-versioned (a project-wide test checks this)."""
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import service as audit
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsStaffUser

from .models import NewsRightsRecord, NewsSource
from .permissions import NewsEnabled
from .serializers import RightsWriteSerializer, SourceWriteSerializer, rights_data, source_data
from .services import rights


class NewsConfigView(APIView):
    """What the website needs to know before drawing News links: the feature switches, nothing secret."""

    permission_classes = [NewsEnabled, AllowAny]

    def get(self, request, **kwargs):
        return Response({"enabled": settings.NEWS_ENABLED, "public": settings.NEWS_PUBLIC_ENABLED, "import": settings.NEWS_IMPORT_ENABLED, "copyright_contact": settings.NEWS_COPYRIGHT_CONTACT, "comments": settings.NEWS_COMMENTS_ENABLED})


class StaffView(APIView):
    permission_classes = [NewsEnabled, IsStaffUser]
    parser_classes = [JSONParser]


def _rights_failure(exc):
    return ValidationError({"detail": str(exc)})


class AdminSourceListCreateView(StaffView):
    def get(self, request, **kwargs):
        qs = NewsSource.objects.annotate(
            record_total=Count("rights_records", distinct=True),
            approved_records=Count("rights_records", filter=Q(rights_records__status=NewsRightsRecord.Status.APPROVED), distinct=True),
        ).order_by("name", "id")
        state = request.query_params.get("state")
        if state in NewsSource.Approval.values:
            qs = qs.filter(approval_state=state)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([{**source_data(s), "record_total": s.record_total, "approved_records": s.approved_records} for s in page])

    def post(self, request, **kwargs):
        serializer = SourceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            source = serializer.save(created_by=request.user)
            audit.log(request, "news.source_create", source, name=source.name, source_type=source.source_type)
        return Response(source_data(source), status=201)


class AdminSourceDetailView(StaffView):
    def get(self, request, pk, **kwargs):
        source = get_object_or_404(NewsSource, pk=pk)
        return Response({**source_data(source), "rights": [rights_data(r) for r in source.rights_records.all()], "decision": rights.evaluate(source).as_dict()})

    def patch(self, request, pk, **kwargs):
        source = get_object_or_404(NewsSource, pk=pk)
        serializer = SourceWriteSerializer(source, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            source = serializer.save()
            audit.log(request, "news.source_update", source, name=source.name, fields=sorted(serializer.validated_data))
        return Response(source_data(source))


class AdminSourceDecisionView(StaffView):
    """What the rights gate says about this source right now, with the reasons. Handy before publishing or switching a source on."""

    def get(self, request, pk, **kwargs):
        source = get_object_or_404(NewsSource, pk=pk)
        return Response(rights.evaluate(source).as_dict())


class AdminSourceActionView(StaffView):
    """POST approve / suspend / reject / activate / deactivate. Approval and suspension are the only ways to change approval_state."""

    def post(self, request, pk, action, **kwargs):
        source = get_object_or_404(NewsSource, pk=pk)
        try:
            with transaction.atomic():
                if action == "approve":
                    rights.approve_source(source, request.user)
                    audit.log(request, "news.source_approve", source, name=source.name)
                elif action == "suspend":
                    rights.suspend_source(source, request.user)
                    audit.log(request, "news.source_suspend", source, name=source.name, reason=(request.data.get("reason") or "")[:200])
                elif action == "reject":
                    rights.reject_source(source, request.user)
                    audit.log(request, "news.source_reject", source, name=source.name)
                elif action in ("activate", "deactivate"):
                    if action == "activate" and source.approval_state != NewsSource.Approval.APPROVED:
                        raise rights.RightsError("Approve the source before switching it on.")
                    source.is_active = action == "activate"
                    source.save(update_fields=["is_active", "updated_at"])
                    audit.log(request, "news.source_update", source, name=source.name, fields=["is_active"])
                else:
                    raise rights.RightsError("Unknown action.")
        except rights.RightsError as exc:
            raise _rights_failure(exc)
        return Response(source_data(source))


class AdminRightsListCreateView(StaffView):
    def get(self, request, pk, **kwargs):
        source = get_object_or_404(NewsSource, pk=pk)
        return Response([rights_data(r) for r in source.rights_records.all()])

    def post(self, request, pk, **kwargs):
        source = get_object_or_404(NewsSource, pk=pk)
        serializer = RightsWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            record = serializer.save(source=source, created_by=request.user)
            audit.log(request, "news.rights_create", record, source=source.name, licence=record.licence, basis=record.basis)
        return Response(rights_data(record), status=201)


class AdminRightsDetailView(StaffView):
    def get(self, request, pk, **kwargs):
        return Response(rights_data(get_object_or_404(NewsRightsRecord, pk=pk)))

    def patch(self, request, pk, **kwargs):
        record = get_object_or_404(NewsRightsRecord, pk=pk)
        if record.status != NewsRightsRecord.Status.DRAFT:
            raise ValidationError({"detail": "Only a draft rights record can be edited. Create a new record for a changed licence."})
        serializer = RightsWriteSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            record = serializer.save()
            audit.log(request, "news.rights_update", record, licence=record.licence, fields=sorted(serializer.validated_data))
        return Response(rights_data(record))


class AdminRightsActionView(StaffView):
    def post(self, request, pk, action, **kwargs):
        record = get_object_or_404(NewsRightsRecord.objects.select_related("source"), pk=pk)
        try:
            with transaction.atomic():
                if action == "approve":
                    rights.approve_record(record, request.user)
                    audit.log(request, "news.rights_approve", record, source=record.source.name, licence=record.licence)
                elif action == "revoke":
                    rights.revoke_record(record, request.user, request.data.get("reason"))
                    audit.log(request, "news.rights_revoke", record, source=record.source.name, licence=record.licence, reason=record.revoked_reason)
                else:
                    raise rights.RightsError("Unknown action.")
        except rights.RightsError as exc:
            raise _rights_failure(exc)
        return Response(rights_data(record))

"""Staff-only moderation API, mounted under /api/v1/admin/. Every view requires IsStaffUser."""
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import service as audit
from apps.core.permissions import IsStaffUser

from . import services
from .models import Comment, CommentReport
from .serializers import (
    AdminCommentSerializer,
    AdminReportSerializer,
    AdminStatusSerializer,
    CommentSettingsSerializer,
)


def with_report_count(queryset):
    return queryset.annotate(report_count=Count("reports", distinct=True))


class AdminCommentListView(generics.ListAPIView):
    """Filters: ?status=, ?story= (id or slug), ?reported=1, ?q= (body or author email). Newest first."""

    permission_classes = [IsStaffUser]
    serializer_class = AdminCommentSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = with_report_count(Comment.objects.select_related("story", "user__profile")).order_by("-created_at", "-id")
        if params.get("status"):
            if params["status"] not in Comment.Status.values:
                raise serializers.ValidationError({"status": ["Unknown status."], "detail": ["Unknown status."]})
            qs = qs.filter(status=params["status"])
        if params.get("story"):
            story = params["story"]
            qs = qs.filter(story_id=int(story)) if story.isdigit() else qs.filter(story__slug=story)
        if params.get("reported") in ("1", "true"):
            qs = qs.filter(report_count__gt=0)
        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(body__icontains=q) | Q(user__email__icontains=q))
        return qs


class AdminCommentDetailView(APIView):
    """PATCH {status: approved|hidden|deleted}. Nothing else about a comment can be changed here."""

    permission_classes = [IsStaffUser]
    http_method_names = ["patch", "options"]

    def patch(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        serializer = AdminStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_status = comment.status
        with transaction.atomic():
            services.set_status(comment, serializer.validated_data["status"])
            if comment.status != old_status:
                audit.log(request, "comment.status", comment, status_from=old_status, status_to=comment.status, story_id=comment.story_id)
        fresh = with_report_count(Comment.objects.select_related("story", "user__profile")).get(pk=pk)
        return Response(AdminCommentSerializer(fresh).data)


class AdminCommentReportsView(generics.ListAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = AdminReportSerializer
    pagination_class = None

    def get_queryset(self):
        if not Comment.objects.filter(pk=self.kwargs["pk"]).exists():
            raise Http404
        return CommentReport.objects.filter(comment_id=self.kwargs["pk"]).select_related("user__profile")[:200]


class AdminDismissReportsView(APIView):
    """The reports were reviewed and need no action: remove them (the comment keeps its status)."""

    permission_classes = [IsStaffUser]
    http_method_names = ["post", "options"]

    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        with transaction.atomic():
            removed, _ = CommentReport.objects.filter(comment=comment).delete()
            audit.log(request, "comment.reports_dismissed", comment, dismissed=removed, story_id=comment.story_id)
        return Response({"dismissed": removed})


class AdminCommentSettingsView(APIView):
    """GET / PATCH {comment_moderation: off | approve_first | approve_first_time}."""

    permission_classes = [IsStaffUser]
    http_method_names = ["get", "patch", "options"]

    def get(self, request):
        return Response({"comment_moderation": services.get_moderation_mode()})

    def patch(self, request):
        serializer = CommentSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        previous = services.get_moderation_mode()
        with transaction.atomic():
            mode = services.set_moderation_mode(serializer.validated_data["comment_moderation"])
            if mode != previous:
                audit.log(request, "settings.comment_moderation", None, mode_from=previous, mode_to=mode)
        return Response({"comment_moderation": mode})

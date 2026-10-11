"""Reader-facing comment endpoints. Moderation endpoints live in admin_views.py."""
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.http import Http404
from rest_framework import generics, serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.http import mark_per_user
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsVerifiedEmail
from apps.stories.public_views import get_public_story_or_404, public_story_filter

from . import services
from .models import Comment, CommentReport
from .serializers import CommentCreateSerializer, CommentEditSerializer, CommentSerializer, ReportSerializer

S = Comment.Status


class CommentPagination(StandardPagination):
    page_size = 20
    page_size_query_param = None  # readers cannot change the page size


def _problem(field, message, code=400):
    exc = serializers.ValidationError({field: [message], "detail": [message]})
    exc.status_code = code
    return exc


class StoryCommentsView(generics.ListAPIView):
    """GET: approved comments (oldest first, 20 per page, replies nested). POST: add a comment."""

    serializer_class = CommentSerializer
    pagination_class = CommentPagination
    authentication_classes = [SessionAuthentication]
    throttle_classes = [ScopedRateThrottle]

    @property
    def throttle_scope(self):
        return "comment" if self.request.method == "POST" else "public_read"  # 10/hour per user to post

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsVerifiedEmail()]  # logged in AND email verified
        return [AllowAny()]

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        # A top-level comment is listed when it is approved, or is the reader's own pending one, or is a deleted
        # placeholder that still has approved replies under it. Hidden comments (and their replies) never appear.
        has_replies = Exists(Comment.objects.filter(parent=OuterRef("pk"), status=S.APPROVED))
        visible = Q(status=S.APPROVED) | Q(status=S.DELETED, has_replies=True)
        reply_visible = Q(status=S.APPROVED)
        if user:
            visible |= Q(status=S.PENDING, user=user)  # readers see their OWN pending comments
            reply_visible |= Q(status=S.PENDING, user=user)
        replies = Comment.objects.filter(reply_visible).select_related("user__profile").order_by("created_at", "id")
        return (
            Comment.objects.filter(story=self.story, parent__isnull=True)
            .annotate(has_replies=has_replies)
            .filter(visible)
            .select_related("user__profile")
            .prefetch_related(Prefetch("replies", queryset=replies, to_attr="visible_replies"))
            .order_by("created_at", "id")
        )

    def list(self, request, *args, **kwargs):
        self.story = get_public_story_or_404(kwargs["slug"])
        response = super().list(request, *args, **kwargs)
        return mark_per_user(response, request)

    def post(self, request, slug):
        story = get_public_story_or_404(slug)
        serializer = CommentCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        reply_to = None
        parent_id = serializer.validated_data.get("parent")
        if parent_id is not None:
            reply_to = Comment.objects.select_related("parent").filter(pk=parent_id, story=story).first()
            if reply_to is None or not services.can_reply_to(reply_to):
                raise _problem("parent", "You can no longer reply to that comment.")
        comment = services.create_comment(user=request.user, story=story, body=serializer.validated_data["body"], reply_to=reply_to)
        comment.user = request.user  # already loaded: no extra query when serialising
        return Response(CommentSerializer(comment, context={"request": request}).data, status=status.HTTP_201_CREATED)


def _get_comment_for(request, pk):
    """The comment, or a 404 when it should not exist for this reader (non-public story, or not visible to them)."""
    comment = (
        Comment.objects.select_related("user__profile", "story")
        .filter(public_story_filter("story"), pk=pk)
        .first()
    )
    if comment is None:
        raise Http404
    user, owner, staff = request.user, request.user.id == comment.user_id, request.user.is_staff
    visible = (
        comment.status == S.APPROVED
        or (comment.status in (S.PENDING, S.DELETED) and owner)  # own pending (edit) / own deleted (idempotent delete)
        or staff
    )
    if not visible:
        raise Http404
    return comment


class CommentDetailView(APIView):
    """PATCH (edit own comment inside the edit window) and DELETE (own soft-delete, or staff)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_read"
    http_method_names = ["patch", "delete", "options"]

    def patch(self, request, pk):
        comment = _get_comment_for(request, pk)
        if comment.user_id != request.user.id:
            raise _problem("detail", "You can only edit your own comments.", 403)
        if comment.status not in (S.APPROVED, S.PENDING):
            raise Http404
        if not services.within_edit_window(comment):
            minutes = int(services.edit_window().total_seconds() // 60)
            raise _problem("detail", f"Comments can only be edited within {minutes} minutes of posting.", 403)
        serializer = CommentEditSerializer(data=request.data, context={"request": request}, comment=comment)
        serializer.is_valid(raise_exception=True)
        services.edit_comment(comment, serializer.validated_data["body"])
        return Response(CommentSerializer(comment, context={"request": request}).data)

    def delete(self, request, pk):
        comment = _get_comment_for(request, pk)
        if comment.user_id != request.user.id and not request.user.is_staff:
            raise _problem("detail", "You can only delete your own comments.", 403)
        services.set_status(comment, S.DELETED)  # soft delete: the row stays, the text is replaced in output
        return Response(CommentSerializer(comment, context={"request": request}).data)


class CommentReportView(APIView):
    """A reader flags a comment. One report per reader per comment; repeating it is a harmless 200."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "report"
    http_method_names = ["post", "options"]

    def post(self, request, pk):
        comment = Comment.objects.filter(public_story_filter("story"), pk=pk, status=S.APPROVED).first()
        if comment is None:
            raise Http404  # only visible (approved) comments can be reported
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, created = CommentReport.objects.get_or_create(
            comment=comment, user=request.user, defaults={"reason": serializer.validated_data["reason"]}
        )
        return Response({"reported": True}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

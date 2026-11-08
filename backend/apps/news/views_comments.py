"""News comments (readers) and their moderation and the monitoring summary (staff)."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit import service as audit
from apps.core.http import mark_per_user
from apps.core.pagination import StandardPagination
from apps.stories.serializers import author_name

from .models import NewsComment
from .permissions import NewsCommentsEnabled, NewsPublicEnabled
from .public_views import get_public_article_or_404
from .services import comments as service
from .services import monitoring
from .views import StaffView

S = NewsComment.Status


class CommentPagination(StandardPagination):
    page_size = 20
    page_size_query_param = None  # readers cannot change the page size


def comment_data(c, user):
    """Public output: an allowlist. Display name only, never an email or a user id."""
    mine = bool(user and user.is_authenticated and c.user_id == user.id)
    return {"id": c.pk, "body": c.body, "author": author_name(c.user), "status": c.status, "is_mine": mine, "can_delete": mine, "created_at": c.created_at}


class ArticleCommentsView(APIView):
    """GET: approved comments (oldest first, 20 per page) plus the reader's own pending ones. POST: add a comment (logged-in readers only).
    Comments follow the article: when the article stops being public (withdrawn, quarantined, licence lapsed) this is a 404 as well."""

    authentication_classes = [SessionAuthentication]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    http_method_names = ["get", "post", "head", "options"]

    @property
    def throttle_scope(self):
        return "news_comment" if self.request.method == "POST" else "public_read"

    def get_permissions(self):
        base = [NewsPublicEnabled(), NewsCommentsEnabled()]
        return base + [IsAuthenticated()] if self.request.method == "POST" else base + [AllowAny()]

    def get(self, request, slug, **kwargs):
        article, _ = get_public_article_or_404(slug)
        user = request.user if request.user.is_authenticated else None
        visible = Q(status=S.APPROVED) | (Q(status=S.PENDING, user=user) if user else Q(pk__in=[]))
        qs = NewsComment.objects.filter(article=article).filter(visible).select_related("user__profile")
        paginator = CommentPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return mark_per_user(paginator.get_paginated_response([comment_data(c, user) for c in page]), request)

    def post(self, request, slug, **kwargs):
        article, _ = get_public_article_or_404(slug)
        try:
            comment = service.create_comment(request.user, article, request.data.get("body"))
        except service.CommentProblem as exc:
            raise ValidationError({"body": [str(exc)], "detail": [str(exc)]})
        comment.user = request.user
        return Response(comment_data(comment, request.user), status=201)


class OwnCommentView(APIView):
    """DELETE /news/comments/<id>/ : a reader removes their own comment (a soft delete; repeating it is harmless)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [NewsPublicEnabled, NewsCommentsEnabled, IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_read"
    http_method_names = ["delete", "options"]

    def delete(self, request, pk, **kwargs):
        comment = get_object_or_404(NewsComment.objects.select_related("user__profile"), pk=pk, user=request.user)
        if comment.status != S.DELETED:
            service.set_status(comment, S.DELETED)
        return Response(comment_data(comment, request.user))


# ------------------------------------------------------------------ staff
class AdminCommentListView(StaffView):
    def get(self, request, **kwargs):
        qs = NewsComment.objects.select_related("user__profile", "article")
        status_ = request.query_params.get("status")
        if status_ in NewsComment.Status.values:
            qs = qs.filter(status=status_)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs.order_by("-created_at", "-id"), request, view=self)
        rows = [{**comment_data(c, request.user), "email": c.user.email, "article": {"id": c.article_id, "title": c.article.title, "slug": c.article.slug}} for c in page]
        return paginator.get_paginated_response(rows)


class AdminCommentActionView(StaffView):
    """POST approve | hide | delete."""

    ACTIONS = {"approve": S.APPROVED, "hide": S.HIDDEN, "delete": S.DELETED}

    def post(self, request, pk, action, **kwargs):
        if action not in self.ACTIONS:
            raise ValidationError({"detail": "Unknown action."})
        comment = get_object_or_404(NewsComment.objects.select_related("user__profile", "article"), pk=pk)
        service.set_status(comment, self.ACTIONS[action])
        if action == "approve":
            audit.log(request, "news.comment_approve", comment, article=comment.article.title)
        elif action == "hide":
            audit.log(request, "news.comment_hide", comment, article=comment.article.title)
        else:
            audit.log(request, "news.comment_delete", comment, article=comment.article.title)
        return Response({**comment_data(comment, request.user), "email": comment.user.email})


class AdminMonitoringView(StaffView):
    """GET: the health snapshot and its problems. (Not a list, so the envelope wraps it as plain data.)"""

    def get(self, request, **kwargs):
        snap = monitoring.snapshot()
        return Response({**snap, "alerts": monitoring.alerts(snap)})

from django.urls import path

from . import admin_views as av
from . import views as v

urlpatterns = [
    # reader endpoints
    path("stories/<slug:slug>/comments/", v.StoryCommentsView.as_view(), name="story-comments"),
    path("comments/<int:pk>/", v.CommentDetailView.as_view(), name="comment-detail"),
    path("comments/<int:pk>/report/", v.CommentReportView.as_view(), name="comment-report"),
    # staff moderation
    path("admin/comments/", av.AdminCommentListView.as_view(), name="admin-comments"),
    path("admin/comments/<int:pk>/", av.AdminCommentDetailView.as_view(), name="admin-comment"),
    path("admin/comments/<int:pk>/reports/", av.AdminCommentReportsView.as_view(), name="admin-comment-reports"),
    path("admin/comments/<int:pk>/dismiss-reports/", av.AdminDismissReportsView.as_view(), name="admin-comment-dismiss"),
    path("admin/comment-settings/", av.AdminCommentSettingsView.as_view(), name="admin-comment-settings"),
]

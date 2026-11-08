"""News routes, all under /api/v1/news/. Each phase adds its own group of paths below."""
from django.urls import path

from . import public_views, views, views_articles, views_comments, views_ingest, views_takedown

urlpatterns = [
    path("news/config/", views.NewsConfigView.as_view(), name="news-config"),
    # Phase 2: sources and rights (staff only)
    path("news/admin/sources/", views.AdminSourceListCreateView.as_view(), name="news-admin-sources"),
    path("news/admin/sources/<int:pk>/", views.AdminSourceDetailView.as_view(), name="news-admin-source"),
    path("news/admin/sources/<int:pk>/decision/", views.AdminSourceDecisionView.as_view(), name="news-admin-source-decision"),
    path("news/admin/sources/<int:pk>/rights/", views.AdminRightsListCreateView.as_view(), name="news-admin-source-rights"),
    path("news/admin/sources/<int:pk>/poll/", views_ingest.AdminSourcePollView.as_view(), name="news-admin-source-poll"),
    path("news/admin/sources/<int:pk>/<slug:action>/", views.AdminSourceActionView.as_view(), name="news-admin-source-action"),
    path("news/admin/rights/<int:pk>/", views.AdminRightsDetailView.as_view(), name="news-admin-rights"),
    path("news/admin/rights/<int:pk>/<slug:action>/", views.AdminRightsActionView.as_view(), name="news-admin-rights-action"),
    # Phase 3: newsroom (staff only)
    path("news/admin/categories/", views_articles.AdminCategoryListCreateView.as_view(), name="news-admin-categories"),
    path("news/admin/categories/<int:pk>/", views_articles.AdminCategoryDetailView.as_view(), name="news-admin-category"),
    path("news/admin/articles/", views_articles.AdminArticleListCreateView.as_view(), name="news-admin-articles"),
    path("news/admin/articles/<int:pk>/", views_articles.AdminArticleDetailView.as_view(), name="news-admin-article"),
    path("news/admin/articles/<int:pk>/revisions/", views_articles.AdminArticleRevisionsView.as_view(), name="news-admin-article-revisions"),
    path("news/admin/articles/<int:pk>/assets/", views_articles.AdminAssetListCreateView.as_view(), name="news-admin-article-assets"),
    path("news/admin/articles/<int:pk>/<slug:action>/", views_articles.AdminArticleActionView.as_view(), name="news-admin-article-action"),
    path("news/admin/assets/<int:pk>/", views_articles.AdminAssetDetailView.as_view(), name="news-admin-asset"),
    path("news/admin/assets/<int:pk>/<slug:action>/", views_articles.AdminAssetActionView.as_view(), name="news-admin-asset-action"),
    # Phase 4: importing and ingestion health (staff only)
    path("news/admin/articles/import-preview/", views_ingest.AdminImportPreviewView.as_view(), name="news-admin-import-preview"),
    path("news/admin/articles/import/", views_ingest.AdminImportView.as_view(), name="news-admin-import"),
    path("news/admin/ingestion/", views_ingest.AdminIngestionView.as_view(), name="news-admin-ingestion"),
    path("news/admin/ingestion/health/", views_ingest.AdminIngestionHealthView.as_view(), name="news-admin-ingestion-health"),
    # Phase 5: takedown workflow (staff queue) and the public complaint form
    path("news/admin/takedowns/", views_takedown.AdminTakedownListView.as_view(), name="news-admin-takedowns"),
    path("news/admin/takedowns/<int:pk>/<slug:action>/", views_takedown.AdminTakedownActionView.as_view(), name="news-admin-takedown-action"),
    path("news/takedown/", views_takedown.TakedownReceiveView.as_view(), name="news-takedown"),
    # Phase 6: comments, moderation and monitoring
    path("news/admin/comments/", views_comments.AdminCommentListView.as_view(), name="news-admin-comments"),
    path("news/admin/comments/<int:pk>/<slug:action>/", views_comments.AdminCommentActionView.as_view(), name="news-admin-comment-action"),
    path("news/admin/monitoring/", views_comments.AdminMonitoringView.as_view(), name="news-admin-monitoring"),
    path("news/comments/<int:pk>/", views_comments.OwnCommentView.as_view(), name="news-comment"),
    # Phase 3: public reading (anonymous, read-only; answers 404 until NEWS_PUBLIC_ENABLED)
    path("news/articles/", public_views.ArticleListView.as_view(), name="news-articles"),
    path("news/articles/<slug:slug>/", public_views.ArticleDetailView.as_view(), name="news-article"),
    path("news/articles/<slug:slug>/view/", public_views.ArticleViewCounterView.as_view(), name="news-article-view"),
    path("news/articles/<slug:slug>/comments/", views_comments.ArticleCommentsView.as_view(), name="news-article-comments"),
    path("news/categories/", public_views.CategoryListView.as_view(), name="news-categories"),
    path("news/featured/", public_views.FeaturedView.as_view(), name="news-featured"),
    path("news/breaking/", public_views.BreakingView.as_view(), name="news-breaking"),
    path("news/related/<slug:slug>/", public_views.RelatedView.as_view(), name="news-related"),
    path("news/sources/", public_views.SourceListView.as_view(), name="news-sources"),
]

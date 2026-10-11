from django.urls import path

from . import public_views as pv
from . import views as v

urlpatterns = [
    path("admin/stories/", v.AdminStoryListCreateView.as_view(), name="admin-stories"),
    path("admin/stories/<int:pk>/", v.AdminStoryDetailView.as_view(), name="admin-story"),
    path("admin/stories/<int:pk>/publish/", v.PublishView.as_view(), name="admin-story-publish"),
    path("admin/stories/<int:pk>/unpublish/", v.UnpublishView.as_view(), name="admin-story-unpublish"),
    path("admin/stories/<int:pk>/archive/", v.ArchiveView.as_view(), name="admin-story-archive"),
    path("admin/stories/<int:pk>/schedule/", v.ScheduleView.as_view(), name="admin-story-schedule"),
    path("admin/stories/<int:pk>/revisions/", v.AdminRevisionListView.as_view(), name="admin-story-revisions"),
    path("admin/stories/<int:pk>/revisions/<int:revision_id>/restore/", v.RestoreRevisionView.as_view(), name="admin-story-restore"),
    path("admin/categories/", v.AdminCategoryListCreateView.as_view(), name="admin-categories"),
    path("admin/categories/<int:pk>/", v.AdminCategoryDetailView.as_view(), name="admin-category"),
    path("admin/tags/", v.AdminTagListCreateView.as_view(), name="admin-tags"),
    path("admin/tags/<int:pk>/", v.AdminTagDetailView.as_view(), name="admin-tag"),

    # ---- PUBLIC read-only API (no login) ----
    path("stories/", pv.PublicStoryListView.as_view(), name="public-stories"),
    path("stories/<slug:slug>/", pv.PublicStoryDetailView.as_view(), name="public-story"),
    path("stories/<slug:slug>/related/", pv.PublicRelatedStoriesView.as_view(), name="public-story-related"),
    path("categories/", pv.PublicCategoryListView.as_view(), name="public-categories"),
    path("categories/<slug:slug>/stories/", pv.PublicCategoryStoriesView.as_view(), name="public-category-stories"),
    path("tags/", pv.PublicTagListView.as_view(), name="public-tags"),
    path("search/", pv.PublicSearchView.as_view(), name="public-search"),
    path("sitemap-data/", pv.PublicSitemapDataView.as_view(), name="public-sitemap-data"),
]

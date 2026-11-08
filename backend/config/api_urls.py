"""All API routes live here, under /api/v1/. Later phases add their app urls to this list."""
from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.stories.urls")),
    path("", include("apps.media.urls")),
    path("", include("apps.reactions.urls")),
    path("", include("apps.comments.urls")),
    path("", include("apps.analytics.urls")),
    path("", include("apps.audit.urls")),
    path("", include("apps.source_marketplace.urls")),  # extension roadmap: source code marketplace
    path("", include("apps.video_tools.urls")),  # extension roadmap: video tools
    path("", include("apps.academy.urls")),  # extension roadmap: Academy (courses, lessons, progress, paid access)
    path("", include("apps.news.urls")),  # extension roadmap: News (sources, rights, articles, public reading)
]

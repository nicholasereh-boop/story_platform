from django.urls import path

from . import admin_views as av
from . import views as v

urlpatterns = [
    path("analytics/collect/", v.CollectView.as_view(), name="analytics-collect"),
    path("admin/analytics/overview/", av.OverviewView.as_view(), name="admin-analytics-overview"),
    path("admin/analytics/daily/", av.DailyView.as_view(), name="admin-analytics-daily"),
    path("admin/analytics/stories/", av.StoriesView.as_view(), name="admin-analytics-stories"),
    path("admin/analytics/traffic/", av.TrafficView.as_view(), name="admin-analytics-traffic"),
]

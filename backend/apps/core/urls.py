from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import AdminPingView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("admin/ping/", AdminPingView.as_view(), name="admin-ping"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

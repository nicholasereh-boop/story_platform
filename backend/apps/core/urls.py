from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import AdminPingView, CspReportView, HealthView, PrivacyPolicyView, PublicConfigView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("public-config/", PublicConfigView.as_view(), name="public-config"),
    path("privacy-policy/", PrivacyPolicyView.as_view(), name="privacy-policy"),
    path("csp-report/", CspReportView.as_view(), name="csp-report"),
    path("admin/ping/", AdminPingView.as_view(), name="admin-ping"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

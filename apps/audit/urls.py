from django.urls import path

from .views import AuditLogListView

urlpatterns = [
    path("admin/audit-logs/", AuditLogListView.as_view(), name="admin-audit-logs"),
]

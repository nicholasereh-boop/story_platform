"""Marketplace routes, all under /api/v1/ (see docs/extension road map/ARCHITECTURE.md).

A numeric segment is always a project ID (edit, upload, checkout ...); the public page is addressed by slug, and slugs
always contain a letter, so the two can never be confused.
"""
from django.urls import path

from . import views

urlpatterns = [
    # public
    path("marketplace/projects/", views.ProjectListCreateView.as_view(), name="marketplace-projects"),
    path("marketplace/config/", views.MarketplaceConfigView.as_view(), name="marketplace-config"),
    path("marketplace/technologies/", views.TechnologyListView.as_view(), name="marketplace-technologies"),
    path("marketplace/projects/<int:pk>/", views.ProjectUpdateView.as_view(), name="marketplace-project-update"),
    path("marketplace/projects/<slug:slug>/", views.ProjectDetailView.as_view(), name="marketplace-project"),
    # the signed-in seller
    path("marketplace/my/projects/", views.MyProjectsView.as_view(), name="marketplace-my-projects"),
    path("marketplace/my/projects/<int:pk>/", views.MyProjectDetailView.as_view(), name="marketplace-my-project"),
    path("marketplace/projects/<int:pk>/submit/", views.ProjectStateView.as_view(action_name="submit"), name="marketplace-submit"),
    path("marketplace/projects/<int:pk>/unpublish/", views.ProjectStateView.as_view(action_name="unpublish"), name="marketplace-unpublish"),
    path("marketplace/projects/<int:pk>/archive/", views.ProjectStateView.as_view(action_name="archive"), name="marketplace-archive"),
    path("marketplace/projects/<int:pk>/screenshots/", views.ScreenshotUploadView.as_view(), name="marketplace-screenshots"),
    path("marketplace/projects/<int:pk>/screenshots/<int:shot_id>/", views.ScreenshotDeleteView.as_view(), name="marketplace-screenshot-delete"),
    path("marketplace/projects/<int:pk>/upload/", views.PackageUploadView.as_view(), name="marketplace-upload"),
    path("marketplace/projects/<int:pk>/github-import/", views.GitHubImportView.as_view(), name="marketplace-github-import"),
    path("marketplace/projects/<int:pk>/packages/<str:kind>/", views.PackageRemoveView.as_view(), name="marketplace-package-remove"),
    # buying and downloading
    path("marketplace/projects/<int:pk>/checkout/", views.CheckoutView.as_view(), name="marketplace-checkout"),
    path("marketplace/payments/verify/", views.VerifyPaymentView.as_view(), name="marketplace-verify"),
    path("marketplace/payments/webhook/", views.PaystackWebhookView.as_view(), name="marketplace-webhook"),
    path("marketplace/purchases/", views.PurchaseListView.as_view(), name="marketplace-purchases"),
    path("marketplace/packages/<int:pk>/download/", views.PackageDownloadView.as_view(), name="marketplace-download"),
    # staff moderation
    path("admin/marketplace/projects/", views.AdminProjectListView.as_view(), name="admin-marketplace-projects"),
    path("admin/marketplace/projects/<int:pk>/<str:action>/", views.AdminProjectActionView.as_view(), name="admin-marketplace-action"),
]

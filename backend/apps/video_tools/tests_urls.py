"""Isolated URL configuration used by the app's API tests only."""
from django.urls import include, path

urlpatterns = [path("", include("apps.video_tools.urls"))]

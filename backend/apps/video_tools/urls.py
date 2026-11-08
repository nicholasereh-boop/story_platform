from django.urls import path

from . import views

urlpatterns = [
    path("video-tools/inspect/", views.InspectView.as_view(), name="video-inspect"),
    path("video-tools/downloads/", views.DownloadListCreateView.as_view(), name="video-downloads"),
    path("video-tools/downloads/<uuid:pk>/", views.DownloadDetailView.as_view(), name="video-download"),
    path("video-tools/downloads/<uuid:pk>/file/", views.DownloadFileView.as_view(), name="video-download-file"),
]

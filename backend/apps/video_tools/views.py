from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttles import FlexibleScopedRateThrottle

from .models import DownloadJob
from .permissions import IsActiveUser, VideoToolsEnabled
from .serializers import DownloadRequestSerializer, JobSerializer, UrlSerializer, inspect_payload
from .services import download_jobs


class Refused(APIException):
    default_detail = "This request was refused."

    def __init__(self, exc):
        self.status_code = exc.status
        super().__init__(detail={"detail": exc.message, "code": exc.code})


def my_jobs(user):
    return DownloadJob.objects.filter(requester=user).select_related("artifact")


class InspectView(APIView):
    """POST {url}: validate the link and say what is possible. No network access, no login needed."""

    permission_classes = [VideoToolsEnabled, AllowAny]
    throttle_classes = [FlexibleScopedRateThrottle]
    throttle_scope = "video_inspect"

    def post(self, request, **kwargs):
        serializer = UrlSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(inspect_payload(serializer.validated_data["url"]))


class DownloadListCreateView(APIView):
    permission_classes = [VideoToolsEnabled, IsActiveUser]

    def get_throttles(self):
        self.throttle_scope = "video_download" if self.request.method == "POST" else "video_poll"
        return [FlexibleScopedRateThrottle()]

    def get(self, request, **kwargs):
        jobs = my_jobs(request.user)[:20]
        return Response(JobSerializer(jobs, many=True).data)

    def post(self, request, **kwargs):
        serializer = DownloadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            job = download_jobs.create_job(request.user, data["url"], data.get("format", ""), timezone.now())
        except download_jobs.JobRefused as exc:
            raise Refused(exc)
        download_jobs.enqueue(job)
        job = my_jobs(request.user).get(pk=job.pk)
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class DownloadDetailView(APIView):
    permission_classes = [VideoToolsEnabled, IsActiveUser]
    throttle_classes = [FlexibleScopedRateThrottle]
    throttle_scope = "video_poll"

    def _job(self, request, pk):
        # Someone else's job is exactly as "not found" as one that never existed.
        return get_object_or_404(my_jobs(request.user), pk=pk)

    def get(self, request, pk, **kwargs):
        return Response(JobSerializer(self._job(request, pk)).data)

    def delete(self, request, pk, **kwargs):
        job = self._job(request, pk)
        download_jobs.cancel_or_remove(job)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DownloadFileView(APIView):
    permission_classes = [VideoToolsEnabled, IsActiveUser]
    throttle_classes = [FlexibleScopedRateThrottle]
    throttle_scope = "video_poll"

    def get(self, request, pk, **kwargs):
        job = get_object_or_404(my_jobs(request.user), pk=pk)
        art = getattr(job, "artifact", None)
        if job.status != DownloadJob.Status.DONE or art is None or art.deleted_at or art.expires_at <= timezone.now():
            raise NotFound()
        try:
            handle = art.file.storage.open(art.file.name, "rb")
        except (FileNotFoundError, OSError):
            raise NotFound()
        response = FileResponse(handle, as_attachment=True, filename=art.filename, content_type=art.content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

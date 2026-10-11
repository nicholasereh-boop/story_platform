from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path


def api_not_found(request, exception=None):
    """Unknown /api/ paths get the standard error envelope instead of an HTML 404 page."""
    if request.path.startswith("/api/"):
        body = {"data": None, "errors": {"detail": "Not found."}, "message": "Not found."}
        return JsonResponse(body, status=404)
    from django.views.defaults import page_not_found

    return page_not_found(request, exception)


urlpatterns = [
    path("accounts/", include("allauth.urls")),  # Google login lives at /accounts/google/login/
    # URLPathVersioning reads the "version" group, so /api/v1/... is version "v1".
    re_path(r"^api/(?P<version>v1)/", include("config.api_urls")),
    re_path(r"^api/", api_not_found),  # anything else under /api/ -> JSON 404
]

if settings.DJANGO_ADMIN_ENABLED:
    # The built-in admin lives at DJANGO_ADMIN_URL (default "django-admin/") and can be switched off entirely.
    urlpatterns.insert(0, path(settings.DJANGO_ADMIN_URL, admin.site.urls))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "config.urls.api_not_found"

from django.contrib import admin

from .models import DownloadArtifact, DownloadJob, ProviderCapability
from .services import providers


@admin.register(ProviderCapability)
class ProviderCapabilityAdmin(admin.ModelAdmin):
    """Where staff switch a provider on, AFTER reviewing its current terms. Switching on does nothing unless a reviewed
    adapter is also configured (settings.VIDEO_TOOLS_ADAPTERS)."""

    list_display = ("provider", "download_enabled", "adapter_present", "terms_reviewed_at", "updated_at")
    list_filter = ("download_enabled",)

    @admin.display(boolean=True, description="Adapter configured")
    def adapter_present(self, obj):
        return providers.get_adapter(obj.provider) is not None



class ReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DownloadJob)
class DownloadJobAdmin(ReadOnly):
    list_display = ("id", "provider", "status", "requester", "created_at", "error_code")
    list_filter = ("provider", "status")


@admin.register(DownloadArtifact)
class DownloadArtifactAdmin(ReadOnly):
    exclude = ("file",)
    list_display = ("job", "filename", "size_bytes", "expires_at", "deleted_at")



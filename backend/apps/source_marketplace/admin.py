from django.contrib import admin

from .models import PaymentEvent, ProjectScreenshot, SourceDownload, SourcePackage, SourceProject, SourcePurchase, Technology


class ReadOnlyAdmin(admin.ModelAdmin):
    """Money and download records are evidence: look, never edit."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SourceProject)
class SourceProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "frontend_price", "backend_price", "currency", "published_at")
    list_filter = ("status",)
    search_fields = ("title", "slug", "owner__email")
    readonly_fields = ("created_at", "updated_at", "published_at", "rights_confirmed_at")


@admin.register(SourcePackage)
class SourcePackageAdmin(ReadOnlyAdmin):
    list_display = ("project", "kind", "version", "size_bytes", "source", "is_active")
    exclude = ("file",)  # the file path is private


@admin.register(SourcePurchase)
class SourcePurchaseAdmin(ReadOnlyAdmin):
    list_display = ("reference", "buyer", "package", "amount", "currency", "status", "verified_at")
    list_filter = ("status",)
    search_fields = ("reference", "buyer__email")


@admin.register(PaymentEvent)
class PaymentEventAdmin(ReadOnlyAdmin):
    list_display = ("event", "reference", "outcome", "received_at", "processed_at")


@admin.register(SourceDownload)
class SourceDownloadAdmin(ReadOnlyAdmin):
    list_display = ("package", "user", "basis", "created_at")


admin.site.register(Technology)
admin.site.register(ProjectScreenshot)

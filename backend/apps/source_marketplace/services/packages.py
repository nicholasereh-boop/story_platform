"""Storing a sanitised archive as a project's package, and public screenshots."""
from django.core.files import File
from django.db import transaction

from apps.media.images import display_name_of

from ..models import ProjectScreenshot, SourcePackage, SourcePurchase


def save_package(project, kind, archive, *, source, source_ref="", original_name="", version=""):
    """Create or replace the project's package of `kind`. The old file is deleted only after the new one is stored."""
    old_name = None
    with transaction.atomic():
        package = SourcePackage.objects.select_for_update().filter(project=project, kind=kind).first()
        if package is None:
            package = SourcePackage(project=project, kind=kind)
        else:
            old_name = package.file.name if package.file else None
        package.version = version or (package.version if package.pk else "1.0.0")
        package.size_bytes = archive.size
        package.sha256 = archive.sha256
        package.file_count = archive.file_count
        package.source = source
        package.source_ref = source_ref[:200]
        package.original_name = original_name[:120]
        package.scan_report = archive.report
        package.is_active = True
        package.file.save("package.zip", File(archive.file), save=False)
        package.save()
    if old_name and old_name != package.file.name:
        try:
            package.file.storage.delete(old_name)
        except Exception:
            pass
    return package


def remove_package(package):
    """Sold packages are only switched off (buyers keep their purchase record); unsold ones are deleted with their file."""
    if SourcePurchase.objects.filter(package=package).exists():
        package.is_active = False
        package.save(update_fields=["is_active", "updated_at"])
        return "deactivated"
    name = package.file.name if package.file else None
    package.delete()
    if name:
        try:
            package.file.storage.delete(name)
        except Exception:
            pass
    return "deleted"


def save_screenshots(project, processed, alt_text=""):
    start = project.screenshots.count()
    created = []
    for index, (content, meta) in enumerate(processed):
        shot = ProjectScreenshot(
            project=project, width=meta.get("width"), height=meta.get("height"), size_bytes=meta.get("size_bytes", 0),
            alt_text=alt_text if len(processed) == 1 else "", position=start + index,
        )
        shot.file.save(content.name, content, save=True)
        created.append(shot)
    return created


__all__ = ["save_package", "remove_package", "save_screenshots", "display_name_of"]

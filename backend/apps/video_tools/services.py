"""Provider-neutral orchestration; actual provider extraction is intentionally opt-in."""
from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from .models import ProviderCapability
from .providers import ADAPTERS
from .providers.base import ProviderUnavailable
from .validators import parse_video_url


def get_adapter(provider):
    """Allow a reviewed adapter class to override the safe default stub via settings."""
    configured = getattr(settings, "VIDEO_TOOLS_ADAPTERS", {}) or {}
    path = configured.get(provider)
    if path:
        try:
            adapter = import_string(path)()
        except Exception:
            return None
        return adapter if getattr(adapter, "provider", None) == provider else None
    adapter_cls = ADAPTERS.get(provider)
    return adapter_cls() if adapter_cls else None


def inspect_url(url):
    parsed = parse_video_url(url)
    adapter = get_adapter(parsed.provider)
    capability = ProviderCapability.objects.filter(provider=parsed.provider, download_enabled=True).first()
    enabled = bool(adapter and adapter.is_configured() and capability)
    result = adapter.inspect(parsed) if adapter else {
        "provider": parsed.provider, "download_available": False, "formats": []
    }
    result.update({
        "provider": parsed.provider,
        "content_id": parsed.content_id,
        "canonical_url": parsed.canonical_url,
        "download_available": enabled and bool(result.get("download_available")),
        "authorization_required": True,
        "watermark_free": False,
        "message": result.get("message") or (
            "A permitted download method is not configured." if not enabled else "Confirm you own this video or have permission to download it."
        ),
    })
    return result


def ensure_download_available(provider):
    adapter = get_adapter(provider)
    capability = ProviderCapability.objects.filter(provider=provider, download_enabled=True).first()
    if not adapter or not adapter.is_configured() or not capability:
        raise ProviderUnavailable("No reviewed, permitted download method is configured for this provider.")
    return adapter


def mark_progress(job_id, value):
    from .models import DownloadJob
    DownloadJob.objects.filter(pk=job_id, status=DownloadJob.Status.PROCESSING).update(
        progress=max(0, min(99, int(value)))
    )

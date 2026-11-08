"""Provider capability registry.

A provider can DOWNLOAD only when all three hold:
  1. a reviewed adapter is registered for it (settings.VIDEO_TOOLS_ADAPTERS: {"youtube": "dotted.path.AdapterClass"});
  2. that adapter says it is configured (credentials, quotas ...);
  3. staff switched the provider on (ProviderCapability.download_enabled) after reviewing its current terms.
Otherwise the provider is "inspect only": the link is validated and explained, but no file is ever produced.

Nothing here scrapes, circumvents access controls, strips watermarks or fetches what a person pasted.
"""
from dataclasses import dataclass, field

from django.conf import settings
from django.utils.module_loading import import_string

from .url_validation import LABELS

# Plain-language, deliberately cautious pointers. Platform rules change: these say where to look, not what to promise.
GUIDANCE = {
    "youtube": "YouTube's terms generally only allow downloading through features YouTube itself provides, such as downloading your own uploads from YouTube Studio.",
    "facebook": "Facebook lets you download videos you uploaded yourself from your own Page or profile tools. Downloading other people's videos is generally not permitted.",
    "instagram": "Instagram lets you save your own reels and posts in the app and request a copy of your data. Downloading other people's content is generally not permitted.",
    "tiktok": "TikTok lets you save your own videos in the app, and other people's videos only when their creator allows downloads. Check the video's menu in the app.",
    "x": "X lets you request an archive of your own posts, including media. Downloading other people's media is generally subject to X's terms and the owner's permission.",
}
WATERMARK_NOTE = (
    "Platforms may add a watermark or attribution to files they provide. This tool never removes watermarks, never "
    "bypasses access restrictions or DRM, and cannot download private or restricted content."
)


class AdapterError(Exception):
    """Raised by an adapter: safe-to-show message and a stable code."""

    def __init__(self, message, code="adapter_error"):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class FetchResult:
    path: str  # a file the adapter wrote inside the work directory it was given
    filename: str
    content_type: str = "application/octet-stream"


class DownloadAdapter:
    """Base class for a REVIEWED, permitted download method for ONE provider. See docs/VIDEO_TOOLS.md."""

    provider = ""
    method = ""  # human description of the permitted method (shown to staff, stored in ProviderCapability.method_note)
    formats = [{"key": "mp4", "label": "MP4 video"}]

    def is_configured(self):
        return True

    def fetch(self, job, format_key, workdir):  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class Capability:
    provider: str
    label: str
    available: bool
    reason: str
    method: str = ""
    formats: list = field(default_factory=list)


def get_adapter(provider):
    path = (getattr(settings, "VIDEO_TOOLS_ADAPTERS", {}) or {}).get(provider)
    if not path:
        return None
    try:
        adapter = import_string(path)()
    except Exception:
        return None
    return adapter if getattr(adapter, "provider", None) == provider else None


def capability_for(provider):
    from ..models import ProviderCapability

    label = LABELS[provider]
    adapter = get_adapter(provider)
    if adapter is None:
        return Capability(provider, label, False, f"No permitted download method is set up for {label} on this site.")
    row = ProviderCapability.objects.filter(provider=provider).first()
    if not (row and row.download_enabled):
        return Capability(provider, label, False, f"Downloads from {label} have not been enabled by the site's administrators yet.")
    if not adapter.is_configured():
        return Capability(provider, label, False, f"Downloads from {label} are temporarily unavailable.")
    return Capability(provider, label, True, "", adapter.method, list(adapter.formats))

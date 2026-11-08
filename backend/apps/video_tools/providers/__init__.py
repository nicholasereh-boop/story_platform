"""Provider adapters. Downloads are disabled until a reviewed adapter is configured."""
from .youtube import YouTubeAdapter
from .facebook import FacebookAdapter
from .instagram import InstagramAdapter
from .tiktok import TikTokAdapter
from .x import XAdapter

ADAPTERS = {
    "youtube": YouTubeAdapter,
    "facebook": FacebookAdapter,
    "instagram": InstagramAdapter,
    "tiktok": TikTokAdapter,
    "x": XAdapter,
}

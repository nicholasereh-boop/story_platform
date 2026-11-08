"""Strict URL parsing. This module does not fetch user-supplied URLs."""
from dataclasses import dataclass
from urllib.parse import urlparse
import re


HOSTS = {
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"},
    "facebook": {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch"},
    "instagram": {"instagram.com", "www.instagram.com"},
    "tiktok": {"tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"},
    "x": {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "t.co"},
}


@dataclass(frozen=True)
class ParsedVideoURL:
    provider: str
    content_id: str
    canonical_url: str


def parse_video_url(value: str) -> ParsedVideoURL:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError("Enter a valid video URL.")
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only valid HTTPS video links are accepted.")
    host = parsed.hostname.lower().rstrip(".")
    provider = next((p for p, hosts in HOSTS.items() if host in hosts), None)
    if not provider:
        raise ValueError("This platform is not supported. Use an approved provider link.")
    path = parsed.path or "/"
    # Require a plausible platform video/post path. Do not resolve short links server-side.
    if host in {"youtu.be", "fb.watch", "vm.tiktok.com", "vt.tiktok.com", "t.co"}:
        raise ValueError("Short links must be opened in your browser; paste the full video URL.")
    if provider == "youtube":
        match = re.search(r"(?:^|/)shorts/([A-Za-z0-9_-]{6,})|(?:^|/)embed/([A-Za-z0-9_-]{6,})", path)
        content_id = match.group(1) or match.group(2) if match else None
        if not content_id:
            content_id = next((v for k, v in __import__('urllib.parse', fromlist=['parse_qs']).parse_qs(parsed.query).items() if k == 'v' for v in v[:1]), None)
        if not content_id:
            raise ValueError("Paste a full YouTube video URL.")
        canonical = f"https://www.youtube.com/watch?v={content_id}"
    else:
        # IDs are extracted conservatively from common post/reel/status URL shapes.
        match = re.search(r"/(?:reel|reels|p|tv|videos|watch|status|statuses|photo|video)/([A-Za-z0-9_-]{5,})", path)
        if not match:
            match = re.search(r"/(@[^/]+/video/([0-9]{5,}))", path)
            content_id = match.group(2) if match else None
        else:
            content_id = match.group(1)
        if not content_id:
            raise ValueError("Could not identify a video/post ID in this URL.")
        canonical = f"https://{host}{path}"
    return ParsedVideoURL(provider=provider, content_id=content_id, canonical_url=canonical)

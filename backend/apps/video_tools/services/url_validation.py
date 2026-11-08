"""Validate and identify a pasted video link.

The rule that makes this safe: we NEVER fetch what the person pasted. The link is parsed (not fetched), must be https
on a host from a fixed allow-list, and is reduced to (provider, content id). Everything after that uses a canonical link
REBUILT from the id. So a pasted address can point nowhere except at the five platforms' own pages, and tracking
parameters, credentials, ports and odd paths never travel any further.

Rejected on purpose: other schemes (http, file, javascript, data ...), user:password@host, ports other than 443, IP
addresses, look-alike or look-through hosts (youtube.com.evil.example, evil.example/youtube.com, youtube.com@evil.example),
non-ASCII hosts, encoded paths, whitespace or control characters, and links longer than 2048 characters.
"""
import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

MAX_URL_LENGTH = 2048
_BAD_CHARS = re.compile(r"[\s\x00-\x1f\x7f\\]")


class InvalidVideoUrl(ValueError):
    """`code` is stable for the frontend; `message` is safe to show."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParsedVideoUrl:
    provider: str
    content_id: str
    canonical_url: str
    content_kind: str  # "video", "reel", "short", "post" ...
    needs_resolution: bool  # a short link (vm.tiktok.com, fb.watch ...): the real address is hidden behind a redirect we do not follow


YT_ID = r"[A-Za-z0-9_-]{11}"
DIGITS = r"\d{5,25}"
HOSTS = {
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"},
    "facebook": {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com", "fb.watch"},
    "instagram": {"instagram.com", "www.instagram.com"},
    "tiktok": {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"},
    "x": {"x.com", "www.x.com", "mobile.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"},
}
HOST_TO_PROVIDER = {host: provider for provider, hosts in HOSTS.items() for host in hosts}
LABELS = {"youtube": "YouTube", "facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok", "x": "X"}


def _youtube(host, path, query):
    if host == "youtu.be":
        m = re.fullmatch(rf"/({YT_ID})/?", path)
    elif path == "/watch":
        vid = (query.get("v") or [""])[0]
        m = re.fullmatch(rf"({YT_ID})", vid)
        if m:
            return ParsedVideoUrl("youtube", m.group(1), f"https://www.youtube.com/watch?v={m.group(1)}", "video", False)
        return None
    else:
        m = re.fullmatch(rf"/(?:shorts|live|embed|v)/({YT_ID})/?", path)
    if not m:
        return None
    kind = "short" if path.startswith("/shorts/") else "video"
    return ParsedVideoUrl("youtube", m.group(1), f"https://www.youtube.com/watch?v={m.group(1)}", kind, False)


def _facebook(host, path, query):
    if host == "fb.watch":
        m = re.fullmatch(r"/([A-Za-z0-9_-]{4,20})/?", path)
        return ParsedVideoUrl("facebook", m.group(1), f"https://fb.watch/{m.group(1)}/", "video", True) if m else None
    if path in ("/watch", "/watch/", "/video.php"):
        vid = (query.get("v") or [""])[0]
        if re.fullmatch(DIGITS, vid):
            return ParsedVideoUrl("facebook", vid, f"https://www.facebook.com/watch/?v={vid}", "video", False)
        return None
    m = re.fullmatch(rf"/reel/({DIGITS})/?", path)
    if m:
        return ParsedVideoUrl("facebook", m.group(1), f"https://www.facebook.com/reel/{m.group(1)}", "reel", False)
    m = re.fullmatch(rf"/[A-Za-z0-9.\-_]{{1,80}}/videos/(?:[A-Za-z0-9.\-_]{{1,80}}/)?({DIGITS})/?", path)
    if m:
        return ParsedVideoUrl("facebook", m.group(1), f"https://www.facebook.com/watch/?v={m.group(1)}", "video", False)
    m = re.fullmatch(r"/share/([vr])/([A-Za-z0-9_-]{4,40})/?", path)
    if m:
        return ParsedVideoUrl("facebook", m.group(2), f"https://www.facebook.com/share/{m.group(1)}/{m.group(2)}/", "video", True)
    return None


def _instagram(host, path, query):
    m = re.fullmatch(r"/(?:[A-Za-z0-9._]{1,30}/)?(reel|reels|p|tv)/([A-Za-z0-9_-]{5,20})/?", path)
    if not m:
        return None
    kind = {"reels": "reel", "reel": "reel", "tv": "video", "p": "post"}[m.group(1)]
    segment = "reel" if kind == "reel" else ("tv" if kind == "video" else "p")
    return ParsedVideoUrl("instagram", m.group(2), f"https://www.instagram.com/{segment}/{m.group(2)}/", kind, False)


def _tiktok(host, path, query):
    if host in ("vm.tiktok.com", "vt.tiktok.com"):
        m = re.fullmatch(r"/([A-Za-z0-9]{5,20})/?", path)
        return ParsedVideoUrl("tiktok", m.group(1), f"https://{host}/{m.group(1)}/", "video", True) if m else None
    m = re.fullmatch(rf"/@([A-Za-z0-9._]{{1,40}})/video/({DIGITS})/?", path)
    if m:
        return ParsedVideoUrl("tiktok", m.group(2), f"https://www.tiktok.com/@{m.group(1)}/video/{m.group(2)}", "video", False)
    m = re.fullmatch(r"/t/([A-Za-z0-9]{5,20})/?", path)
    if m:
        return ParsedVideoUrl("tiktok", m.group(1), f"https://www.tiktok.com/t/{m.group(1)}/", "video", True)
    return None


def _x(host, path, query):
    m = re.fullmatch(rf"/([A-Za-z0-9_]{{1,15}}|i(?:/web)?)/status/({DIGITS})(?:/(?:video|photo)/\d{{1,2}})?/?", path)
    if not m:
        return None
    who = m.group(1)
    return ParsedVideoUrl("x", m.group(2), f"https://x.com/{who}/status/{m.group(2)}", "post", False)


MATCHERS = {"youtube": _youtube, "facebook": _facebook, "instagram": _instagram, "tiktok": _tiktok, "x": _x}


def parse_video_url(raw):
    """Return ParsedVideoUrl or raise InvalidVideoUrl. Never performs any network access."""
    if not isinstance(raw, str):
        raise InvalidVideoUrl("malformed", "Paste a video link.")
    text = raw.strip()
    if not text:
        raise InvalidVideoUrl("malformed", "Paste a video link.")
    if len(text) > MAX_URL_LENGTH:
        raise InvalidVideoUrl("malformed", "That link is too long.")
    if _BAD_CHARS.search(text):
        raise InvalidVideoUrl("malformed", "That does not look like a valid link.")
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise InvalidVideoUrl("malformed", "That does not look like a valid link.")
    if parts.scheme.lower() != "https":
        raise InvalidVideoUrl("scheme", "Only secure links that start with https:// are accepted.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise InvalidVideoUrl("credentials", "Links that contain a user name or password are not accepted.")
    if port not in (None, 443):
        raise InvalidVideoUrl("port", "Links with a custom port are not accepted.")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or not host.isascii():
        raise InvalidVideoUrl("host", "That link's address is not valid.")
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip:
        raise InvalidVideoUrl("ip_address", "Links to IP addresses are not accepted.")
    provider = HOST_TO_PROVIDER.get(host)
    if provider is None:
        raise InvalidVideoUrl("unsupported_host", "We only work with links from YouTube, Facebook, Instagram, TikTok and X.")
    if "%" in parts.path or ".." in parts.path or "//" in parts.path:
        raise InvalidVideoUrl("unsupported_link", f"That is a {LABELS[provider]} link, but not the address of a single video or post.")
    parsed = MATCHERS[provider](host, parts.path, parse_qs(parts.query, keep_blank_values=False, max_num_fields=20))
    if parsed is None:
        raise InvalidVideoUrl("unsupported_link", f"That is a {LABELS[provider]} link, but not the address of a single video or post.")
    return parsed

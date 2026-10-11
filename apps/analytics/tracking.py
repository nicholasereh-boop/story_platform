"""Pure helpers for the collect endpoint: hashing, path rules, user-agent category, referrer domain.

Privacy: the raw visitor id, session id, IP address and user-agent string never reach the database. Ids are hashed
with HMAC-SHA256 and a server secret; the user agent is reduced to one coarse word; the referrer to a domain.
"""
import hashlib
import hmac
import re
from urllib.parse import urlparse

from django.conf import settings

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
SLUG = r"[-a-zA-Z0-9_]{1,220}"
MAX_PATH = 300

# Public-site paths that are counted. Everything else (admin, login, register, account, unknown) is ignored.
_STORY_RE = re.compile(rf"^/stories/({SLUG})$")
_PAGE_RES = [
    re.compile(p)
    for p in (
        r"^/$", r"^/stories$", r"^/categories$", rf"^/categories/{SLUG}$", r"^/tags$", rf"^/tags/{SLUG}$",
        r"^/search$", r"^/privacy$",
    )
]

_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|curl/|wget|python-requests|python-urllib|httpclient|headless|lighthouse|preview|"
    r"facebookexternalhit|monitor|uptime|scrapy|go-http-client|java/|axios|node-fetch|pingdom|phantomjs",
    re.IGNORECASE,
)
_TABLET_RE = re.compile(r"ipad|tablet|kindle|silk|playbook", re.IGNORECASE)
_MOBILE_RE = re.compile(r"mobi|iphone|ipod|windows phone", re.IGNORECASE)
_DESKTOP_RE = re.compile(r"windows|macintosh|x11|linux|cros", re.IGNORECASE)
_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,98}[a-z0-9])?$")


def hash_id(value, purpose):
    """Stable, non-reversible hash of an id. `purpose` ("visitor" / "session") keeps the two hash spaces apart."""
    secret = settings.ANALYTICS_HASH_SECRET or settings.SECRET_KEY
    key = hashlib.sha256(f"analytics-v1:{secret}".encode()).digest()
    return hmac.new(key, f"{purpose}:{value.lower()}".encode(), hashlib.sha256).hexdigest()


def valid_id(value):
    return isinstance(value, str) and bool(UUID_RE.match(value))


def classify_path(raw):
    """Normalise a path and decide if it is counted. Returns (path, story_slug_or_None), or None to ignore it."""
    if not isinstance(raw, str):
        return None
    path = raw.split("?", 1)[0].split("#", 1)[0].strip()
    if len(path) > MAX_PATH or not path.startswith("/") or path.startswith("//"):
        return None
    if len(path) > 1:
        path = path.rstrip("/")
    story = _STORY_RE.match(path)
    if story:
        return path, story.group(1)
    if any(r.match(path) for r in _PAGE_RES):
        return path, None
    return None


def is_bot(user_agent):
    return bool(user_agent) and bool(_BOT_RE.search(user_agent))


def device_category(user_agent):
    """desktop | mobile | tablet | other. (Bots are filtered out earlier with is_bot.)"""
    ua = user_agent or ""
    if _TABLET_RE.search(ua) or ("android" in ua.lower() and "mobile" not in ua.lower()):
        return "tablet"
    if _MOBILE_RE.search(ua) or "android" in ua.lower():
        return "mobile"
    if _DESKTOP_RE.search(ua):
        return "desktop"
    return "other"


def referrer_domain(raw, own_hosts=()):
    """Domain of an external referrer, or "" (none, malformed, or our own site). The path and query are discarded."""
    if not isinstance(raw, str) or not raw or len(raw) > 2000:
        return ""
    try:
        host = (urlparse(raw).hostname or "").lower()
    except ValueError:
        return ""
    host = host[4:] if host.startswith("www.") else host
    own = {h.lower().removeprefix("www.") for h in own_hosts if h}
    if not host or host in own or not _HOST_RE.match(host):
        return ""
    return host

"""Rich text from outside is never trusted. clean_body() rebuilds article HTML from an allowlist with bleach: unknown tags are
removed (their text kept), every attribute is dropped except safe link addresses, and every link gets rel="nofollow noopener noreferrer".
There are no scripts, styles, iframes, images or embeds in the body: pictures and videos are NewsAssets with their own rights."""
import hashlib
import re

import bleach

ALLOWED_TAGS = ["p", "br", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "strong", "em", "b", "i", "u", "a", "hr", "code", "pre"]
ALLOWED_ATTRIBUTES = {"a": ["href", "title"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]
MAX_BODY_CHARS = 200_000
_TAG = re.compile(r"<[^>]+>")
_STRIP_BLOCKS = re.compile(r"<(script|style|iframe|object|embed|svg|math|template)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


def _nofollow(attrs, new=False):
    attrs[(None, "rel")] = "nofollow noopener noreferrer"
    return attrs


def clean_body(html):
    """Sanitised HTML (string). Never raises on odd input."""
    raw = str(html or "")[:MAX_BODY_CHARS * 2]
    raw = _STRIP_BLOCKS.sub("", raw)  # bleach keeps the TEXT of a stripped tag; for script/style that text is code, so remove it all
    cleaned = bleach.clean(raw, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, protocols=ALLOWED_PROTOCOLS, strip=True, strip_comments=True)
    cleaned = bleach.linkify(cleaned, callbacks=[_nofollow], skip_tags=["pre", "code"], parse_email=False)
    return cleaned[:MAX_BODY_CHARS]


def plain_text(html):
    """The visible text of sanitised html, for search and for word counts."""
    return re.sub(r"\s+", " ", _TAG.sub(" ", str(html or ""))).strip()


def content_hash(title, body):
    """Hash of the visible content (title + text), so a re-import of the same article is recognised even when markup differs."""
    text = (re.sub(r"\s+", " ", str(title or "")).strip().lower() + "\n" + plain_text(body).lower()).encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def url_hash(url):
    return hashlib.sha256(normalise_url(url).encode("utf-8")).hexdigest() if url else ""


def normalise_url(url):
    """Lower-case host, no fragment, no trailing slash, no tracking parameters: so one article has one address."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(str(url or "").strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))

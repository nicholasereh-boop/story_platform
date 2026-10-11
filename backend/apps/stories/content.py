"""Story content schema and validation.

Stories are stored as TipTap / ProseMirror JSON in Story.content_json, NEVER as raw HTML.
clean_content() REBUILDS the document from an allowlist, so unknown node types, unknown
marks, unsafe links and arbitrary iframes can never reach the database.

Allowed nodes (and the only attributes kept for each; everything else is dropped):
    doc            root, {"type": "doc", "content": [...]}
    paragraph      textAlign (left | center | right | justify)
    heading        level (1-6), textAlign
    text           text (non-empty string, max 20000 chars), marks
    hardBreak
    bulletList, listItem, blockquote, horizontalRule
    orderedList    start (integer >= 1)
    image          assetId (positive integer, required), alt (<= 300), caption (<= 500),
                   align (left | center | right, default center),
                   size (small | medium | full, default full)
                   Existence of the asset is checked by the story serializer (this module only checks the shape).
    youtube        stored ONLY as {"videoId": "<11 chars>"}; accepts videoId or a youtube URL

Allowed marks: bold, italic, underline, strike, link
    link           href must start with http://, https:// or mailto: (any case), max 2000 chars,
                   no whitespace or control characters. javascript:, data: etc. are REJECTED.

Limits: depth 12, 5000 nodes, 20000 chars per text node, 1 MB serialized.
"""
import copy
import json
import re

from rest_framework import serializers

MAX_DEPTH = 12
MAX_NODES = 5000
MAX_TEXT_LEN = 20000
MAX_BYTES = 1024 * 1024

BLOCK_CONTAINERS = {"doc", "paragraph", "heading", "bulletList", "orderedList", "listItem", "blockquote"}
LEAF_NODES = {"text", "hardBreak", "horizontalRule", "image", "youtube"}
ALLOWED_NODES = BLOCK_CONTAINERS | LEAF_NODES
ALLOWED_MARKS = {"bold", "italic", "underline", "strike", "link"}
ALIGNMENTS = {"left", "center", "right", "justify"}
IMAGE_ALIGN = {"left", "center", "right"}
IMAGE_SIZE = {"small", "medium", "full"}
LINK_PREFIXES = ("http://", "https://", "mailto:")

YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
YT_URL = re.compile(
    r"^https://(?:www\.|m\.)?"
    r"(?:youtube\.com/(?:watch\?(?:[^#]*&)?v=|embed/|shorts/)|youtube-nocookie\.com/embed/|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})(?:[&?#/].*)?$"
)


def empty_doc():
    """A new, empty story document (also the model default)."""
    return {"type": "doc", "content": [{"type": "paragraph"}]}


def _err(message):
    raise serializers.ValidationError(message)


def youtube_id(value):
    """The 11-character video ID from a YouTube URL (or a bare ID), else None."""
    value = str(value or "").strip()
    if YT_ID.match(value):
        return value
    match = YT_URL.match(value)
    return match.group(1) if match else None


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _clean_marks(marks):
    if marks is None:
        return []
    if not isinstance(marks, list):
        _err("Invalid text formatting.")
    cleaned = []
    for mark in marks:
        if not isinstance(mark, dict) or mark.get("type") not in ALLOWED_MARKS:
            _err("This story uses text formatting that is not supported.")
        if mark["type"] == "link":
            attrs = mark.get("attrs")
            href = str(attrs.get("href", "")) if isinstance(attrs, dict) else ""  # not stripped: stray whitespace is rejected below
            if not href.lower().startswith(LINK_PREFIXES) or len(href) > 2000 or re.search(r"[\s\x00-\x1f\x7f]", href):
                _err("Links must start with http://, https:// or mailto: and contain no spaces.")
            cleaned.append({"type": "link", "attrs": {"href": href}})
        else:
            cleaned.append({"type": mark["type"]})
    return cleaned


def _clean_node(node, depth, state):
    if not isinstance(node, dict):
        _err("Invalid story content.")
    state["nodes"] += 1
    if state["nodes"] > MAX_NODES or depth > MAX_DEPTH:
        _err("This story is too large or too deeply nested.")
    node_type = node.get("type")
    if node_type not in ALLOWED_NODES:
        _err(f"Content type '{node_type}' is not supported.")
    attrs = node.get("attrs")
    if attrs is None:
        attrs = {}
    if not isinstance(attrs, dict):
        _err("Invalid story content.")
    out = {"type": node_type}

    if node_type == "text":
        text = node.get("text")
        if not isinstance(text, str) or not text:
            _err("Invalid text in story.")
        if len(text) > MAX_TEXT_LEN:
            _err(f"A single text block may have at most {MAX_TEXT_LEN} characters.")
        out["text"] = text
        marks = _clean_marks(node.get("marks"))
        if marks:
            out["marks"] = marks
        return out

    kept = {}
    if node_type in ("paragraph", "heading"):
        if attrs.get("textAlign") in ALIGNMENTS and attrs["textAlign"] != "left":
            kept["textAlign"] = attrs["textAlign"]
        if node_type == "heading":
            level = attrs.get("level", 2)
            if not _is_int(level) or not 1 <= level <= 6:
                _err("Heading level must be between 1 and 6.")
            kept["level"] = level
    elif node_type == "orderedList":
        start = attrs.get("start", 1)
        if _is_int(start) and 1 < start <= 9999:
            kept["start"] = start
    elif node_type == "image":
        asset_id = attrs.get("assetId")
        if not _is_int(asset_id) or asset_id <= 0:
            _err("Images must reference a media library item (assetId).")
        kept = {
            "assetId": asset_id,
            "alt": str(attrs.get("alt") or "")[:300],
            "caption": str(attrs.get("caption") or "")[:500],
            "align": attrs.get("align") if attrs.get("align") in IMAGE_ALIGN else "center",
            "size": attrs.get("size") if attrs.get("size") in IMAGE_SIZE else "full",
        }
    elif node_type == "youtube":
        video_id = youtube_id(attrs.get("videoId") or attrs.get("src"))
        if not video_id:
            _err("Only YouTube video links are allowed.")
        kept = {"videoId": video_id}
    if kept:
        out["attrs"] = kept

    if node_type in BLOCK_CONTAINERS:
        children = node.get("content")
        if children is None:
            children = []
        if not isinstance(children, list):
            _err("Invalid story content.")
        cleaned = [_clean_node(child, depth + 1, state) for child in children]
        if cleaned or node_type == "doc":
            out["content"] = cleaned
    return out


def clean_content(doc):
    """Validate `doc` and return a rebuilt, safe copy. Raises a DRF ValidationError otherwise."""
    if not isinstance(doc, dict) or doc.get("type") != "doc":
        _err('Story content must be a document: {"type": "doc", "content": [...]}.')
    try:
        size = len(json.dumps(doc))
    except (TypeError, ValueError):
        _err("Story content is not valid JSON.")
    if size > MAX_BYTES:
        _err("This story is too large (over 1 MB).")
    return _clean_node(doc, 0, {"nodes": 0})


def _walk(node):
    yield node
    for child in node.get("content") or []:
        yield from _walk(child)


def asset_ids(doc):
    """IDs of all images used in the document (for the media phase; unused for now)."""
    if not isinstance(doc, dict):
        return set()
    return {n["attrs"]["assetId"] for n in _walk(doc) if n.get("type") == "image" and "assetId" in (n.get("attrs") or {})}


def plain_text(doc):
    """The readable text of a document, one line per block. Used for excerpts and search."""
    if not isinstance(doc, dict):
        return ""
    parts = []

    def visit(node):
        kind = node.get("type")
        if kind == "text":
            parts.append(node.get("text", ""))
            return
        if kind == "hardBreak":
            parts.append("\n")
            return
        for child in node.get("content") or []:
            visit(child)
        if kind in BLOCK_CONTAINERS and kind != "doc":
            parts.append("\n")

    visit(doc)
    return re.sub(r"[ \t]*\n[\s]*", "\n", "".join(parts)).strip()


def has_content(doc):
    """True if the story has any visible text, an image or a video (used before publishing)."""
    if not isinstance(doc, dict):
        return False
    for node in _walk(doc):
        if node.get("type") in ("image", "youtube"):
            return True
        if node.get("type") == "text" and node.get("text", "").strip():
            return True
    return False


def resolve_media(doc):
    """Return a COPY of the document for display: image nodes get read-only src/width/height.

    src is None when the asset no longer exists; alt/caption fall back to the asset's own text.
    These extra attributes are never trusted on input: clean_content() drops everything except
    assetId, alt, caption, align and size.
    """
    from apps.media.models import MediaAsset  # imported here to avoid a circular import

    if not isinstance(doc, dict):
        return doc
    doc = copy.deepcopy(doc)
    ids = asset_ids(doc)
    assets = {asset.pk: asset for asset in MediaAsset.objects.filter(pk__in=ids)} if ids else {}
    for node in _walk(doc):
        attrs = node.get("attrs")
        if node.get("type") != "image" or not isinstance(attrs, dict):
            continue
        asset = assets.get(attrs.get("assetId"))
        attrs["src"] = asset.file.url if asset else None
        attrs["width"] = asset.width if asset else None
        attrs["height"] = asset.height if asset else None
        if asset:
            attrs["alt"] = attrs.get("alt") or asset.alt_text
            attrs["caption"] = attrs.get("caption") or asset.caption
    return doc

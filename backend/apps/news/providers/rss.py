"""RSS 2.0 and Atom 1.0 parser using only the standard library. XML bombs (entity expansion) are blocked by refusing any DOCTYPE or ENTITY declaration."""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from .base import AdapterError, BaseAdapter, RawItem

CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
DC_CREATOR = "{http://purl.org/dc/elements/1.1/}creator"
ATOM = "{http://www.w3.org/2005/Atom}"
_FORBIDDEN = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
MAX_ITEMS_PARSED = 200


def _text(node, tag):
    child = node.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def _plain(html, limit=500):
    return re.sub(r"\s+", " ", _TAG.sub(" ", html or "")).strip()[:limit]


def _date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class RssAdapter(BaseAdapter):
    name = "rss"

    def parse(self, payload, source):
        if _FORBIDDEN.search(payload[:200_000]):
            raise AdapterError("The feed contains a DOCTYPE or ENTITY declaration, which is not allowed.")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            raise AdapterError("The feed is not valid XML.")
        tag = root.tag.split("}")[-1].lower()
        if tag == "rss" or root.find("channel") is not None:
            items = self._rss(root)
        elif tag == "feed":
            items = self._atom(root)
        else:
            raise AdapterError("This is neither an RSS nor an Atom feed.")
        return items[:MAX_ITEMS_PARSED]

    def _rss(self, root):
        channel = root.find("channel") if root.find("channel") is not None else root
        language = _text(channel, "language")
        out = []
        for item in channel.findall("item"):
            link = _text(item, "link")
            guid = _text(item, "guid") or link
            title = _text(item, "title")
            if not (guid and title):
                continue
            body = (item.findtext(CONTENT) or "").strip()
            out.append(RawItem(external_id=guid[:200], title=title[:220], canonical_url=link if link.startswith("https://") else "",
                               standfirst=_plain(_text(item, "description")), body=body, author=(item.findtext(DC_CREATOR) or _text(item, "author"))[:160],
                               published_at=_date(_text(item, "pubDate")), language=language[:8]))
        return out

    def _atom(self, root):
        out = []
        for entry in root.findall(ATOM + "entry"):
            link = ""
            for ln in entry.findall(ATOM + "link"):
                if ln.get("rel", "alternate") == "alternate" and (ln.get("href") or "").startswith("https://"):
                    link = ln.get("href")
                    break
            guid = (entry.findtext(ATOM + "id") or link).strip()
            title = (entry.findtext(ATOM + "title") or "").strip()
            if not (guid and title):
                continue
            content = entry.find(ATOM + "content")
            body = ((content.text or "") if content is not None and content.get("type", "text") in ("html", "xhtml", "text") else "").strip()
            author = entry.find(ATOM + "author")
            out.append(RawItem(external_id=guid[:200], title=title[:220], canonical_url=link, standfirst=_plain(entry.findtext(ATOM + "summary") or ""),
                               body=body, author=((author.findtext(ATOM + "name") or "") if author is not None else "")[:160],
                               published_at=_date(entry.findtext(ATOM + "published") or entry.findtext(ATOM + "updated")), language=(root.get("{http://www.w3.org/XML/1998/namespace}lang") or "")[:8]))
        return out

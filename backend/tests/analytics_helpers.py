"""Helpers for the Phase 9 (analytics) tests."""
import uuid
from datetime import date, datetime, timedelta, timezone as dt_timezone

from apps.analytics.models import PageViewEvent, Visitor
from apps.analytics.tracking import hash_id

BASE = "/api/v1/"
COLLECT = BASE + "analytics/collect/"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
TABLET_UA = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
BOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
VISITOR_ID = "11111111-1111-4111-8111-111111111111"
SESSION_ID = "22222222-2222-4222-8222-222222222222"


def new_id():
    return str(uuid.uuid4())


def collect(client, path="/", visitor=VISITOR_ID, session=SESSION_ID, referrer="", ua=DESKTOP_UA, **extra):
    """POST one page-view event, like the browser tracker does."""
    body = {"path": path, "visitor_id": visitor, "session_id": session, "referrer": referrer}
    return client.post(COLLECT, body, format="json", HTTP_USER_AGENT=ua, **extra)


def at(day, hour=12):
    """An aware UTC datetime on `day` (a date)."""
    return datetime(day.year, day.month, day.day, hour, tzinfo=dt_timezone.utc)


def visitor(n):
    """A Visitor row for test visitor number n (stable)."""
    row, _ = Visitor.objects.get_or_create(visitor_key_hash=hash_id(f"00000000-0000-4000-8000-{n:012d}", "visitor"))
    return row


def event(n, when, story=None, path=None, referrer="", device="desktop"):
    """A stored page view by test visitor n at `when` (datetime) or `when` (date -> noon UTC)."""
    when = at(when) if isinstance(when, date) and not isinstance(when, datetime) else when
    return PageViewEvent.objects.create(
        visitor=visitor(n),
        story=story,
        path=path or (f"/stories/{story.slug}" if story else "/"),
        session_key_hash="s" * 64,
        referrer_domain=referrer,
        user_agent_category=device,
        created_at=when,
    )

"""POST /analytics/collect/: what is counted, what is ignored, privacy, dedupe, throttle, switches."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.analytics import tracking, views as analytics_views
from apps.analytics.models import PageViewEvent, Visitor

from .analytics_helpers import (
    BOT_UA, COLLECT, DESKTOP_UA, MOBILE_UA, SESSION_ID, TABLET_UA, VISITOR_ID, collect, new_id,
)
from .engagement_helpers import client_for, make_story, make_user

pytestmark = pytest.mark.django_db


def stored():
    return PageViewEvent.objects.count()


# ---------------------------------------------------------------- counted
def test_valid_event_returns_empty_204_and_is_stored():
    r = collect(client_for(), "/")
    assert r.status_code == 204 and r.content == b""
    event = PageViewEvent.objects.get()
    assert event.path == "/" and event.story is None and event.user_agent_category == "desktop"
    assert Visitor.objects.count() == 1


def test_story_view_counts_and_increments_view_count_once_per_window():
    story = make_story()
    for _ in range(5):  # refreshing 5 times
        assert collect(client_for(), f"/stories/{story.slug}").status_code == 204
    assert stored() == 1
    story.refresh_from_db()
    assert story.view_count == 1  # only the counted view
    assert PageViewEvent.objects.get().story_id == story.id


def test_path_is_normalised_query_and_trailing_slash_removed():
    collect(client_for(), "/stories/?page=2&utm_source=x#top")
    assert list(PageViewEvent.objects.values_list("path", flat=True)) == ["/stories"]


@pytest.mark.parametrize("path", ["/", "/stories", "/categories", "/categories/news", "/tags", "/tags/python", "/search", "/privacy"])
def test_public_pages_are_counted(path):
    collect(client_for(), path)
    assert stored() == 1


# ---------------------------------------------------------------- ignored (always 204, nothing stored)
@pytest.mark.parametrize(
    "path",
    ["/admin/stories", "/admin", "/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/account",
     "/nope", "//evil.example/x", "stories/no-leading-slash", "/stories/" + "a" * 400, None, 123, "/stories/bad slug"],
)
def test_excluded_and_unknown_paths_are_ignored(path):
    assert collect(client_for(), path).status_code == 204
    assert stored() == 0 and Visitor.objects.count() == 0


def test_non_public_and_unknown_stories_are_ignored():
    for status in ("draft", "scheduled", "archived"):
        story = make_story(f"S {status}", status=status)
        assert collect(client_for(), f"/stories/{story.slug}").status_code == 204
    assert collect(client_for(), "/stories/does-not-exist").status_code == 204
    assert stored() == 0


def test_bots_are_dropped():
    for ua in (BOT_UA, "curl/8.4.0", "python-requests/2.31", "HeadlessChrome/120", "Mozilla/5.0 (compatible; bingbot/2.0)"):
        assert collect(client_for(), "/", ua=ua).status_code == 204
    assert stored() == 0


@pytest.mark.parametrize("visitor,session", [("not-a-uuid", SESSION_ID), (VISITOR_ID, "nope"), (None, SESSION_ID), (VISITOR_ID, None), (5, 6)])
def test_malformed_ids_are_ignored(visitor, session):
    assert collect(client_for(), "/", visitor=visitor, session=session).status_code == 204
    assert stored() == 0


def test_malformed_body_still_gets_204():
    for body in ("not json", "[1,2]", ""):
        r = client_for().post(COLLECT, body, content_type="application/json", HTTP_USER_AGENT=DESKTOP_UA)
        assert r.status_code == 204
    assert stored() == 0


def test_do_not_track_and_global_privacy_control_are_respected():
    assert collect(client_for(), "/", HTTP_DNT="1").status_code == 204
    assert collect(client_for(), "/", HTTP_SEC_GPC="1").status_code == 204
    assert stored() == 0


def test_logged_in_staff_are_not_tracked_but_readers_are():
    staff, reader = make_user("s@example.com", staff=True), make_user("r@example.com")
    c = APIClient()
    c.force_login(staff)
    assert collect(c, "/").status_code == 204 and stored() == 0
    c2 = APIClient()
    c2.force_login(reader)
    collect(c2, "/")
    assert stored() == 1


def test_master_switch(settings):
    settings.ANALYTICS_ENABLED = False
    assert collect(client_for(), "/").status_code == 204
    assert stored() == 0 and Visitor.objects.count() == 0


def test_no_csrf_and_no_cookies():
    c = APIClient(enforce_csrf_checks=True)
    r = collect(c, "/")
    assert r.status_code == 204 and not r.cookies


# ---------------------------------------------------------------- privacy
def test_no_raw_ip_user_agent_ids_or_full_referrer_are_stored():
    collect(client_for(), "/", referrer="https://News.Example.org/some/path?token=secret#frag", REMOTE_ADDR="203.0.113.77")
    event = PageViewEvent.objects.get()
    assert event.referrer_domain == "news.example.org"
    haystack = " ".join(
        str(v) for model in (PageViewEvent, Visitor) for row in model.objects.values() for v in row.values()
    )
    for secret in ("203.0.113.77", "Mozilla", "Chrome", "Windows", VISITOR_ID, SESSION_ID, "token=secret", "/some/path", "https://"):
        assert secret not in haystack, secret
    assert len(Visitor.objects.get().visitor_key_hash) == 64 and event.session_key_hash != SESSION_ID


def test_hashing_is_stable_distinct_and_secret_dependent(settings):
    a, b = new_id(), new_id()
    assert tracking.hash_id(a, "visitor") == tracking.hash_id(a, "visitor") == tracking.hash_id(a.upper(), "visitor")
    assert tracking.hash_id(a, "visitor") != tracking.hash_id(b, "visitor")
    assert tracking.hash_id(a, "visitor") != tracking.hash_id(a, "session")  # separate hash spaces
    before = tracking.hash_id(a, "visitor")
    settings.ANALYTICS_HASH_SECRET = "another-secret"
    assert tracking.hash_id(a, "visitor") != before


def test_same_browser_is_one_visitor_across_pages():
    collect(client_for(), "/")
    collect(client_for(), "/stories")
    other = new_id()
    collect(client_for(), "/", visitor=other)
    assert Visitor.objects.count() == 2 and stored() == 3


def test_referrer_rules():
    assert tracking.referrer_domain("https://www.google.com/search?q=x") == "google.com"
    assert tracking.referrer_domain("http://localhost:5173/stories/x", ["localhost"]) == ""  # our own site
    assert tracking.referrer_domain("javascript:alert(1)") == ""
    assert tracking.referrer_domain("") == "" and tracking.referrer_domain(None) == ""
    assert tracking.referrer_domain("http://bad host/") == ""


@pytest.mark.parametrize(
    "ua,expected", [(DESKTOP_UA, "desktop"), (MOBILE_UA, "mobile"), (TABLET_UA, "tablet"), ("SomethingOdd/1.0", "other"), ("", "other")]
)
def test_device_category(ua, expected):
    assert tracking.device_category(ua) == expected


def test_android_phone_vs_tablet():
    phone = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
    tablet = "Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    assert tracking.device_category(phone) == "mobile" and tracking.device_category(tablet) == "tablet"


# ---------------------------------------------------------------- dedupe
def test_repeat_views_count_once_until_the_window_passes():
    for _ in range(20):
        collect(client_for(), "/stories")
    assert stored() == 1
    collect(client_for(), "/tags")  # another page counts
    collect(client_for(), "/stories", visitor=new_id())  # another visitor counts
    assert stored() == 3
    cache.clear()  # the cache entry "expires"
    collect(client_for(), "/stories")
    assert stored() == 4


def test_database_fallback_when_the_cache_is_down(monkeypatch):
    def broken(*args, **kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr(analytics_views.cache, "add", broken)
    collect(client_for(), "/stories")
    collect(client_for(), "/stories")  # repeat: the database check blocks it
    assert stored() == 1
    PageViewEvent.objects.update(created_at=timezone.now() - timedelta(minutes=31))
    collect(client_for(), "/stories")  # outside the 30 minute window
    assert stored() == 2


def test_dedupe_window_is_configurable(settings):
    settings.ANALYTICS_DEDUPE_MINUTES = 1
    collect(client_for(), "/")
    assert stored() == 1
    PageViewEvent.objects.update(created_at=timezone.now() - timedelta(minutes=2))
    cache.clear()
    collect(client_for(), "/")
    assert stored() == 2


# ---------------------------------------------------------------- throttle
def test_collect_is_throttled(monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "analytics", "2/min")
    assert collect(client_for(), "/").status_code == 204
    assert collect(client_for(), "/stories").status_code == 204
    assert collect(client_for(), "/tags").status_code == 429

"""Admin analytics API: permissions, overview with comparison, gap-free series, top stories, traffic, validation, privacy,
fixed query counts."""
import json
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.analytics import aggregation as agg
from apps.analytics.models import DailyAnalytics, PageViewEvent, Visitor
from apps.reactions.models import Like

from .analytics_helpers import BASE, DESKTOP_UA, at, event
from .engagement_helpers import add_comment, client_for, make_story, make_user

pytestmark = pytest.mark.django_db

A = BASE + "admin/analytics/"
ENDPOINTS = ["overview/", "daily/", "stories/", "traffic/"]
MON = date(2026, 3, 2)  # a Monday


@pytest.fixture
def admin():
    return client_for(make_user("staff@example.com", staff=True))


def today():
    return timezone.now().date()


def days_ago(n):
    return today() - timedelta(days=n)


def data(response):
    assert response.status_code == 200, response.content
    return response.json()["data"]


# ---------------------------------------------------------------- permissions
@pytest.mark.parametrize("path", ENDPOINTS)
def test_non_staff_and_anonymous_get_403(path):
    for client in (client_for(), client_for(make_user("reader@example.com"))):
        assert client.get(A + path).status_code in (401, 403)


@pytest.mark.parametrize("path", ENDPOINTS)
def test_endpoints_are_read_only(admin, path):
    assert admin.post(A + path, {}, format="json").status_code == 405


# ---------------------------------------------------------------- overview
def test_overview_compares_with_the_previous_period(admin):
    for n in (1, 2, 3):  # 3 distinct visitors this week
        event(n, at(days_ago(n)))
    event(1, at(days_ago(2)))  # visitor 1 again (page views 4, visitors 3)
    for n in (10, 11):  # 2 visitors in the previous 7 days
        event(n, at(days_ago(8 + n - 10)))
    agg.aggregate_range(days_ago(14), today())
    o = data(admin.get(A + "overview/", {"days": 7}))
    assert o["range"]["days"] == 7 and o["range"]["to"] == today().isoformat()
    assert o["previous_range"]["to"] == days_ago(7).isoformat()
    assert (o["current"]["unique_visitors"], o["current"]["page_views"]) == (3, 4)
    assert (o["previous"]["unique_visitors"], o["previous"]["page_views"]) == (2, 2)
    assert o["change"]["unique_visitors"] == 50.0 and o["change"]["page_views"] == 100.0
    assert o["current"]["unique_visitors_exact"] is True


def test_overview_change_is_null_without_previous_data(admin):
    event(1, at(days_ago(1)))
    o = data(admin.get(A + "overview/", {"days": 7}))
    assert o["change"]["page_views"] is None and o["previous"]["page_views"] == 0


def test_overview_counts_likes_comments_and_new_accounts(admin):
    story, user = make_story(), make_user("u@example.com")
    Like.objects.create(user=user, story=story)
    add_comment(story, user, "hello", status="approved")
    o = data(admin.get(A + "overview/", {"days": 7}))["current"]
    assert o["likes"] == 1 and o["comments"] == 1 and o["registered_users"] >= 2  # u@ and staff@


def test_today_is_computed_live_without_running_the_aggregation(admin):
    event(1, timezone.now())  # right now, nobody ran aggregate_analytics
    assert data(admin.get(A + "overview/", {"days": 1}))["current"]["page_views"] == 1
    event(2, timezone.now())
    DailyAnalytics.objects.filter(date=today()).update(updated_at=timezone.now() - timedelta(minutes=10))  # stale
    assert data(admin.get(A + "overview/", {"days": 1}))["current"]["page_views"] == 2


# ---------------------------------------------------------------- series
def test_daily_series_has_no_gaps(admin):
    event(1, at(days_ago(2)))
    event(2, at(days_ago(2)))
    agg.aggregate_range(days_ago(6), today())
    d = data(admin.get(A + "daily/", {"days": 7}))
    dates = [p["date"] for p in d["points"]]
    assert d["granularity"] == "day" and len(dates) == 7 and dates[-1] == today().isoformat()
    assert dates == sorted(dates) and all(date.fromisoformat(b) - date.fromisoformat(a) == timedelta(days=1) for a, b in zip(dates, dates[1:]))
    by_date = {p["date"]: p for p in d["points"]}
    assert by_date[days_ago(2).isoformat()]["unique_visitors"] == 2
    assert by_date[days_ago(5).isoformat()] == {"date": days_ago(5).isoformat(), "unique_visitors": 0, "page_views": 0,
                                                "story_views": 0, "registered_users": 0, "likes": 0, "comments": 0}


def test_weekly_and_monthly_granularity_use_exact_uniques(admin):
    event(1, date(2026, 3, 2))
    event(1, date(2026, 3, 3))
    event(2, date(2026, 3, 4))
    event(3, date(2026, 3, 10))
    event(1, date(2026, 2, 20))
    agg.aggregate_range(date(2026, 2, 16), date(2026, 3, 15))
    weeks = data(admin.get(A + "daily/", {"from": "2026-03-04", "to": "2026-03-12", "granularity": "week"}))
    assert [p["date"] for p in weeks["points"]] == ["2026-03-02", "2026-03-09"]  # snapped back to Monday
    assert (weeks["points"][0]["unique_visitors"], weeks["points"][0]["page_views"]) == (2, 3)
    assert (weeks["points"][1]["unique_visitors"], weeks["points"][1]["page_views"]) == (1, 1)
    months = data(admin.get(A + "daily/", {"from": "2026-02-10", "to": "2026-03-20", "granularity": "month"}))
    assert [p["date"] for p in months["points"]] == ["2026-02-01", "2026-03-01"]
    assert (months["points"][1]["unique_visitors"], months["points"][1]["page_views"]) == (3, 4)  # exact, not 1+1+1+1


def test_a_missing_week_is_a_zero_point(admin):
    event(1, date(2026, 3, 2))
    agg.aggregate_range(date(2026, 3, 2), date(2026, 3, 2))
    pts = data(admin.get(A + "daily/", {"from": "2026-03-02", "to": "2026-03-23", "granularity": "week"}))["points"]
    assert [p["page_views"] for p in pts] == [1, 0, 0, 0]


# ---------------------------------------------------------------- top stories
def test_top_stories_ordering_limit_and_counts(admin):
    a, b, c = make_story("A"), make_story("B"), make_story("C")
    draft = make_story("Draft", status="draft")
    for n in range(5):
        event(n, at(days_ago(1)), story=a)
    for n in range(3):
        event(n, at(days_ago(1)), story=b)
    event(1, at(days_ago(1)), story=c)
    event(2, at(days_ago(1)), story=c)
    event(2, at(days_ago(2)), story=c)  # c: 3 views like b. Ties on views and daily uniques are broken by story id (b was created first)
    event(1, at(days_ago(1)), story=draft)
    user = make_user("u@example.com")
    Like.objects.create(user=user, story=a)
    add_comment(a, user, "nice", status="approved")
    agg.aggregate_range(days_ago(6), today())
    rows = data(admin.get(A + "stories/", {"days": 7}))["stories"]
    assert [r["title"] for r in rows][:3] == ["A", "B", "C"]
    first = rows[0]
    assert (first["views"], first["unique_visitors"], first["likes"], first["comments"]) == (5, 5, 1, 1)
    assert set(first) == {"id", "title", "slug", "views", "unique_visitors", "likes", "comments"}
    assert len(data(admin.get(A + "stories/", {"days": 7, "limit": 2}))["stories"]) == 2
    assert "Draft" not in [r["title"] for r in rows]


# ---------------------------------------------------------------- traffic
def test_traffic_breakdown(admin):
    event(1, at(days_ago(1)), referrer="google.com", device="mobile")
    event(2, at(days_ago(1)), referrer="google.com", device="desktop")
    event(3, at(days_ago(1)), referrer="", device="desktop")
    event(3, at(days_ago(1)), referrer="news.example.org", device="tablet")
    t = data(admin.get(A + "traffic/", {"days": 7}))
    assert t["referrers"][0] == {"domain": "google.com", "page_views": 2, "visitors": 2}
    assert {"domain": "Direct", "page_views": 1, "visitors": 1} in t["referrers"]
    assert {d["device"]: d["page_views"] for d in t["devices"]} == {"desktop": 2, "mobile": 1, "tablet": 1, "other": 0}


# ---------------------------------------------------------------- validation
@pytest.mark.parametrize(
    "path,params",
    [
        ("overview/", {"days": 0}), ("overview/", {"days": "abc"}), ("overview/", {"days": 400}),
        ("overview/", {"from": "not-a-date"}), ("overview/", {"from": "2026-03-10", "to": "2026-03-01"}),
        ("overview/", {"days": 7, "from": "2026-03-01"}), ("overview/", {"from": "2024-01-01", "to": "2026-01-01"}),
        ("daily/", {"granularity": "year"}), ("stories/", {"limit": 0}), ("stories/", {"limit": 51}), ("stories/", {"limit": "x"}),
    ],
)
def test_bad_parameters_are_400_in_the_standard_envelope(admin, path, params):
    r = admin.get(A + path, params)
    body = r.json()
    assert r.status_code == 400 and body["data"] is None and body["message"] and body["errors"]


# ---------------------------------------------------------------- privacy and performance
def test_responses_contain_no_private_data(admin):
    story = make_story()
    v = None
    for n in range(3):
        v = event(n, at(days_ago(1)), story=story, referrer="google.com").visitor
    agg.aggregate_range(days_ago(3), today())
    hashes = list(Visitor.objects.values_list("visitor_key_hash", flat=True)) + list(
        PageViewEvent.objects.values_list("session_key_hash", flat=True)
    )
    for path in ENDPOINTS:
        raw = json.dumps(admin.get(A + path, {"days": 7}).json())
        assert not any(h in raw for h in hashes), path
        for forbidden in ("visitor_key_hash", "session_key_hash", "visitor_id", "ip_address", "user_agent", "Mozilla", "staff@example.com"):
            assert forbidden not in raw, (path, forbidden)


def test_admin_endpoints_use_a_fixed_number_of_queries(admin):
    def count(path, params):
        with CaptureQueriesContext(connection) as ctx:
            assert admin.get(A + path, params).status_code == 200
        return len(ctx)

    stories = [make_story(f"S{i}") for i in range(2)]
    for i, s in enumerate(stories):
        event(i, at(days_ago(1)), story=s, referrer="a.example")
    agg.aggregate_range(days_ago(30), today())
    cases = [("overview/", {"days": 30}), ("daily/", {"days": 30}), ("daily/", {"days": 30, "granularity": "week"}),
             ("stories/", {"days": 30}), ("traffic/", {"days": 30})]
    for path, params in cases:
        count(path, params)  # warm-up (refreshes today's aggregate once)
    before = [count(path, params) for path, params in cases]

    more = [make_story(f"M{i}") for i in range(8)]
    for i, s in enumerate(more):
        for n in range(3):
            event(100 + i * 3 + n, at(days_ago(2 + i)), story=s, referrer=f"site{i}.example", device="mobile")
    agg.aggregate_range(days_ago(30), today())
    after = [count(path, params) for path, params in cases]
    assert before == after

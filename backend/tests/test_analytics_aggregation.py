"""Aggregation (day / week / month), idempotency, back-fill, the commands, and retention (purge)."""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.analytics import aggregation as agg
from apps.analytics.models import (
    AnalyticsState, DailyAnalytics, DailyStoryStats, PageViewEvent, PeriodAnalytics, Visitor,
)
from apps.analytics.purge import purge, retention_days
from apps.comments.models import Comment
from apps.reactions.models import Like

from .analytics_helpers import at, event
from .engagement_helpers import add_comment, make_story, make_user

pytestmark = pytest.mark.django_db

MON = date(2026, 3, 2)  # a Monday
TUE, WED, SUN = MON + timedelta(days=1), MON + timedelta(days=2), MON + timedelta(days=6)


def day_row(d):
    return DailyAnalytics.objects.get(date=d)


# ---------------------------------------------------------------- one day
def test_day_totals_and_story_stats():
    s1, s2 = make_story("One"), make_story("Two")
    event(1, TUE)
    event(1, TUE, path="/stories")
    event(2, TUE, story=s1)
    event(3, TUE, story=s1)
    event(3, TUE, story=s2)
    event(4, WED)  # another day: must not leak into Tuesday
    agg.aggregate_day(TUE)
    row = day_row(TUE)
    assert (row.page_views, row.story_views, row.unique_visitors) == (5, 3, 3)
    stats = {s.story_id: (s.views, s.unique_visitors) for s in DailyStoryStats.objects.filter(date=TUE)}
    assert stats == {s1.id: (2, 2), s2.id: (1, 1)}


def test_day_boundaries_are_utc_midnight():
    event(1, datetime(2026, 3, 2, 23, 59, 59, tzinfo=dt_timezone.utc))
    event(2, datetime(2026, 3, 3, 0, 0, 0, tzinfo=dt_timezone.utc))
    agg.aggregate_day(MON)
    agg.aggregate_day(TUE)
    assert day_row(MON).page_views == 1 and day_row(TUE).page_views == 1


def test_registered_users_likes_and_approved_comments_are_counted_by_date():
    story, user = make_story(), make_user("u@example.com")
    type(user).objects.filter(pk=user.pk).update(date_joined=at(TUE))
    like = Like.objects.create(user=user, story=story)
    Like.objects.filter(pk=like.pk).update(created_at=at(TUE))
    approved = add_comment(story, user, "ok", status="approved")
    pending = add_comment(story, user, "wait", status="pending")
    Comment.objects.filter(pk__in=[approved.pk, pending.pk]).update(created_at=at(TUE))
    agg.aggregate_day(TUE)
    row = day_row(TUE)
    assert (row.registered_users, row.likes, row.comments) == (1, 1, 1)  # the pending comment is not counted
    agg.aggregate_day(WED)
    assert (day_row(WED).registered_users, day_row(WED).likes, day_row(WED).comments) == (0, 0, 0)


# ---------------------------------------------------------------- weeks and months
def test_week_unique_visitors_are_exact_not_summed():
    event(1, MON)
    event(1, TUE)  # same visitor on two days
    event(2, WED)
    agg.aggregate_range(MON, SUN)
    assert [day_row(d).unique_visitors for d in (MON, TUE, WED)] == [1, 1, 1]  # daily uniques sum to 3 ...
    week = PeriodAnalytics.objects.get(period="week", start_date=MON)
    assert week.unique_visitors == 2 and week.page_views == 3  # ... but the week has 2 distinct visitors


def test_weeks_start_on_monday_and_sunday_belongs_to_the_week_before():
    sunday_before = MON - timedelta(days=1)  # 2026-03-01, a Sunday
    event(1, sunday_before)
    event(2, MON)
    agg.aggregate_range(sunday_before, MON)
    assert PeriodAnalytics.objects.get(period="week", start_date=MON - timedelta(days=7)).page_views == 1
    assert PeriodAnalytics.objects.get(period="week", start_date=MON).page_views == 1
    assert agg.week_start(date(2026, 3, 8)) == MON  # Sunday 8 March is still in the week of 2 March


def test_months_are_calendar_months_with_exact_uniques():
    event(1, date(2026, 2, 28))
    event(1, date(2026, 3, 1))
    event(2, date(2026, 3, 15))
    agg.aggregate_range(date(2026, 2, 28), date(2026, 3, 15))
    feb = PeriodAnalytics.objects.get(period="month", start_date=date(2026, 2, 1))
    mar = PeriodAnalytics.objects.get(period="month", start_date=date(2026, 3, 1))
    assert (feb.unique_visitors, feb.page_views) == (1, 1)
    assert (mar.unique_visitors, mar.page_views) == (2, 2)
    assert agg.next_month(date(2026, 12, 20)) == date(2027, 1, 1)


# ---------------------------------------------------------------- idempotency and back-fill
def snapshot():
    return (
        list(DailyAnalytics.objects.order_by("date").values("date", "unique_visitors", "page_views", "story_views", "likes")),
        list(PeriodAnalytics.objects.order_by("period", "start_date").values("period", "start_date", "unique_visitors", "page_views")),
        list(DailyStoryStats.objects.order_by("date", "story_id").values("date", "story_id", "views", "unique_visitors")),
    )


def test_running_twice_gives_identical_rows():
    story = make_story()
    event(1, MON, story=story)
    event(2, TUE, story=story)
    agg.aggregate_range(MON, SUN)
    first = snapshot()
    agg.aggregate_range(MON, SUN)
    assert snapshot() == first
    assert DailyStoryStats.objects.count() == 2 and DailyAnalytics.objects.count() == 7


def test_rerun_picks_up_new_events_without_double_counting():
    event(1, MON)
    agg.aggregate_range(MON, MON)
    event(2, MON)
    agg.aggregate_range(MON, MON)
    assert day_row(MON).page_views == 2


def test_backfill_command_over_a_range():
    for i in range(10):
        event(1, MON + timedelta(days=i))
    out = StringIO()
    call_command("aggregate_analytics", "--from", "2026-03-02", "--to", "2026-03-11", stdout=out)
    assert DailyAnalytics.objects.count() == 10 and all(r.page_views == 1 for r in DailyAnalytics.objects.all())
    assert PeriodAnalytics.objects.filter(period="week").count() == 2  # weeks of 2 and 9 March
    assert "10 day(s)" in out.getvalue()


def test_command_defaults_to_yesterday_and_today_and_validates_input():
    call_command("aggregate_analytics", stdout=StringIO())
    today = timezone.now().date()
    assert set(DailyAnalytics.objects.values_list("date", flat=True)) == {today - timedelta(days=1), today}
    with pytest.raises(CommandError):
        call_command("aggregate_analytics", "--from", "nonsense")
    with pytest.raises(CommandError):
        call_command("aggregate_analytics", "--from", "2026-03-05", "--to", "2026-03-01")


# ---------------------------------------------------------------- retention
def test_purge_keeps_aggregates_and_removes_old_raw_rows():
    story = make_story()
    now = datetime(2026, 6, 1, 12, tzinfo=dt_timezone.utc)  # retention 90 days -> cutoff is 3 March
    cutoff = date(2026, 3, 3)
    event(1, date(2026, 2, 20), story=story)
    event(2, date(2026, 3, 2))  # Monday, old: its week straddles the cutoff
    event(3, date(2026, 3, 4))  # same week, still inside the retention period
    event(4, date(2026, 5, 20))
    stale = visitor_seen_long_ago()
    result = purge(now=now)

    assert result["events"] == 2 and result["cutoff"] == cutoff
    assert list(PageViewEvent.objects.order_by("created_at").values_list("path", flat=True)) == ["/", "/"]
    assert PageViewEvent.objects.count() == 2 and not Visitor.objects.filter(pk=stale.pk).exists()
    # The numbers of the purged days survive, and the straddling week was aggregated with ALL its events first.
    assert day_row(date(2026, 2, 20)).page_views == 1 and day_row(date(2026, 3, 2)).page_views == 1
    assert PeriodAnalytics.objects.get(period="week", start_date=MON).page_views == 2
    assert DailyStoryStats.objects.filter(date=date(2026, 2, 20)).exists()
    assert agg.purged_before() == cutoff

    # Re-aggregating purged days must NOT replace the stored numbers with zeros.
    before = snapshot()
    agg.aggregate_range(date(2026, 2, 20), date(2026, 3, 4))
    assert day_row(date(2026, 2, 20)).page_views == 1 and day_row(date(2026, 3, 2)).page_views == 1
    assert PeriodAnalytics.objects.get(period="week", start_date=MON).page_views == 2
    assert day_row(date(2026, 3, 4)).page_views == 1
    assert before[1] == snapshot()[1]


def visitor_seen_long_ago():
    v = visitor_row = Visitor.objects.create(visitor_key_hash="old" * 21 + "x")
    Visitor.objects.filter(pk=v.pk).update(last_seen_at=datetime(2025, 1, 1, tzinfo=dt_timezone.utc))
    return visitor_row


def test_purge_dry_run_deletes_nothing():
    event(1, date(2026, 1, 5))
    result = purge(now=datetime(2026, 6, 1, tzinfo=dt_timezone.utc), dry_run=True)
    assert result["events"] == 1 and PageViewEvent.objects.count() == 1 and not DailyAnalytics.objects.exists()
    assert not AnalyticsState.objects.exists()


def test_retention_never_drops_below_35_days(settings):
    settings.ANALYTICS_RETENTION_DAYS = 5
    assert retention_days() == 35
    now = datetime(2026, 6, 1, 12, tzinfo=dt_timezone.utc)
    event(1, date(2026, 5, 20))  # 12 days old: kept even though the setting says 5
    assert purge(now=now)["events"] == 0 and PageViewEvent.objects.count() == 1


def test_purge_command_output():
    event(1, date(2026, 1, 5))
    out = StringIO()
    call_command("purge_analytics", stdout=out)
    assert "Deleted 1 event(s)" in out.getvalue() and PageViewEvent.objects.count() == 0
    assert day_row(date(2026, 1, 5)).page_views == 1

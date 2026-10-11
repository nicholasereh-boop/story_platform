"""Turn raw page-view events into daily, weekly and monthly numbers. Every function is idempotent (upsert):
running it twice gives exactly the same rows, so it is always safe to re-run or back-fill.

Rules: all days are UTC; a week starts on MONDAY; a month is a calendar month. Weekly and monthly unique_visitors are
EXACT (distinct visitors in the whole period), never a sum of daily uniques.

Raw events are deleted after the retention period (see purge.py). Once a day is older than the `purged_before` marker
its stored aggregate is the only record left, so aggregation skips it instead of overwriting it with zeros.
"""
from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.comments.models import Comment
from apps.reactions.models import Like

from .models import AnalyticsState, DailyAnalytics, DailyStoryStats, PageViewEvent, PeriodAnalytics

PURGED_KEY = "purged_before"
STALE_AFTER = timedelta(minutes=5)  # how old today's aggregate may get before an admin request refreshes it


# ---------------------------------------------------------------- dates
def utc_start(d):
    """Midnight UTC at the start of date `d`, as an aware datetime."""
    return datetime.combine(d, time.min, tzinfo=dt_timezone.utc)


def week_start(d):
    return d - timedelta(days=d.weekday())  # Monday


def month_start(d):
    return d.replace(day=1)


def next_month(d):
    first = month_start(d)
    return (first + timedelta(days=32)).replace(day=1)


def period_start(period, d):
    return week_start(d) if period == "week" else month_start(d)


def period_end(period, start):
    """First day AFTER the period."""
    return start + timedelta(days=7) if period == "week" else next_month(start)


def daterange(start, end):
    """Every date from start to end, both included."""
    for i in range((end - start).days + 1):
        yield start + timedelta(days=i)


# ---------------------------------------------------------------- purge marker
def purged_before():
    """Events before this date no longer exist (None = nothing was ever purged)."""
    value = AnalyticsState.objects.filter(key=PURGED_KEY).values_list("value", flat=True).first()
    return date.fromisoformat(value) if value else None


def set_purged_before(d):
    AnalyticsState.objects.update_or_create(key=PURGED_KEY, defaults={"value": d.isoformat()})


# ---------------------------------------------------------------- one day
def events_between(start, end):
    return PageViewEvent.objects.filter(created_at__gte=utc_start(start), created_at__lt=utc_start(end))


@transaction.atomic
def aggregate_day(d):
    """Rebuild DailyAnalytics and DailyStoryStats for one UTC day from the raw events and the other tables."""
    events = events_between(d, d + timedelta(days=1))
    day_start, day_end = utc_start(d), utc_start(d + timedelta(days=1))
    totals = events.aggregate(
        page_views=Count("id"),
        story_views=Count("id", filter=_story_filter()),
        unique_visitors=Count("visitor_id", distinct=True),
    )
    User = get_user_model()
    DailyAnalytics.objects.update_or_create(
        date=d,
        defaults={
            **totals,
            "registered_users": User.objects.filter(date_joined__gte=day_start, date_joined__lt=day_end).count(),
            "likes": Like.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count(),
            "comments": Comment.objects.filter(
                status=Comment.Status.APPROVED, created_at__gte=day_start, created_at__lt=day_end
            ).count(),
        },
    )
    per_story = (
        events.filter(story__isnull=False).values("story_id").annotate(views=Count("id"), uv=Count("visitor_id", distinct=True))
    )
    DailyStoryStats.objects.filter(date=d).delete()  # rebuild, so a re-run never double counts
    DailyStoryStats.objects.bulk_create(
        [DailyStoryStats(date=d, story_id=r["story_id"], views=r["views"], unique_visitors=r["uv"]) for r in per_story]
    )


def _story_filter():
    return Q(story__isnull=False)


# ---------------------------------------------------------------- one week / month
def aggregate_period(period, start):
    """Rebuild one PeriodAnalytics row with EXACT distinct visitors for the whole period."""
    end = period_end(period, start)
    totals = events_between(start, end).aggregate(
        page_views=Count("id"),
        story_views=Count("id", filter=_story_filter()),
        unique_visitors=Count("visitor_id", distinct=True),
    )
    PeriodAnalytics.objects.update_or_create(period=period, start_date=start, defaults=totals)


# ---------------------------------------------------------------- a range
def aggregate_range(start, end):
    """Aggregate every day in [start, end] and every week/month that overlaps it. Returns a small summary dict.

    Days (and periods) that begin before the purge marker are skipped, because their raw events are gone and a rebuild
    would replace the stored numbers with zeros.
    """
    horizon = purged_before()
    summary = {"days": 0, "periods": 0, "skipped": 0}
    for d in daterange(start, end):
        if horizon and d < horizon:
            summary["skipped"] += 1
            continue
        aggregate_day(d)
        summary["days"] += 1
    for period in ("week", "month"):
        seen = set()
        for d in daterange(start, end):
            seen.add(period_start(period, d))
        for first in sorted(seen):
            if horizon and first < horizon:
                summary["skipped"] += 1
                continue
            aggregate_period(period, first)
            summary["periods"] += 1
    return summary


# ---------------------------------------------------------------- keeping the dashboard live without Celery
def ensure_fresh(now=None):
    """Called by the admin endpoints when the range includes today.

    Recomputes today (and its week and month) when its aggregate is older than 5 minutes, and recomputes yesterday if
    it was last computed before that day ended. A few queries at most, so the dashboard is right even when Celery beat
    is not running. Older days rely on the Celery schedule or `manage.py aggregate_analytics`.
    """
    now = now or timezone.now()
    today = now.date()
    rows = dict(DailyAnalytics.objects.filter(date__gte=today - timedelta(days=1)).values_list("date", "updated_at"))
    yesterday = today - timedelta(days=1)
    need_yesterday = yesterday not in rows or rows[yesterday] < utc_start(today)
    need_today = today not in rows or now - rows[today] > STALE_AFTER
    if need_yesterday or need_today:
        aggregate_range(yesterday if need_yesterday else today, today)

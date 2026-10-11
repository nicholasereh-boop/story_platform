"""Read side of analytics: everything the admin dashboard shows. Only aggregates and counts leave this module;
no visitor hash, session hash, IP address or user detail is ever returned."""
from datetime import date, timedelta

from django.db.models import Count, Sum
from rest_framework import serializers

from apps.comments.models import Comment
from apps.reactions.models import Like

from .aggregation import (
    events_between, daterange, period_end, period_start, purged_before, utc_start,
)
from .models import DailyAnalytics, DailyStoryStats, PageViewEvent, PeriodAnalytics

MAX_RANGE_DAYS = 366
DEFAULT_DAYS = 30
TOP_STORIES_MAX = 50
KPI_FIELDS = ("unique_visitors", "page_views", "story_views", "registered_users", "likes", "comments")
DEVICES = ("desktop", "mobile", "tablet", "other")


def _bad(param, message):
    return serializers.ValidationError({param: [message], "detail": [message]})


def _int(params, name, default, low, high):
    raw = params.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise _bad(name, f"{name} must be a whole number.")
    if not low <= value <= high:
        raise _bad(name, f"{name} must be between {low} and {high}.")
    return value


def _day(params, name):
    raw = params.get(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise _bad(name, f"{name} must be a date like 2026-03-31.")


def parse_range(params, today):
    """(start, end) inclusive, from ?days= or ?from=&to=. Never longer than 366 days; the end never passes today."""
    start, end = _day(params, "from"), _day(params, "to")
    if params.get("days") and (start or end):
        raise _bad("days", "Use either days or from/to, not both.")
    if start or end:
        end = min(end or today, today)
        start = start or end - timedelta(days=DEFAULT_DAYS - 1)
    else:
        days = _int(params, "days", DEFAULT_DAYS, 1, MAX_RANGE_DAYS)
        end, start = today, today - timedelta(days=days - 1)
    if start > end:
        raise _bad("from", "from must not be after to.")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise _bad("from", f"The range can be at most {MAX_RANGE_DAYS} days.")
    return start, end


def range_info(start, end):
    return {"from": start.isoformat(), "to": end.isoformat(), "days": (end - start).days + 1}


def _pct(current, previous):
    """Percent change, or None when there is nothing to compare with."""
    return None if not previous else round((current - previous) / previous * 100, 1)


# ---------------------------------------------------------------- overview
def totals(start, end, horizon):
    """KPI totals for [start, end]. Unique visitors are exact while the raw events still exist for the whole range;
    otherwise they are the sum of daily uniques (an overestimate) and unique_visitors_exact is false."""
    agg = DailyAnalytics.objects.filter(date__range=(start, end)).aggregate(
        page_views=Sum("page_views"), story_views=Sum("story_views"), registered_users=Sum("registered_users"),
        likes=Sum("likes"), comments=Sum("comments"), daily_uniques=Sum("unique_visitors"),
    )
    exact = horizon is None or start >= horizon
    if exact:
        visitors = events_between(start, end + timedelta(days=1)).values("visitor_id").distinct().count()
    else:
        visitors = agg["daily_uniques"] or 0
    result = {k: agg[k] or 0 for k in ("page_views", "story_views", "registered_users", "likes", "comments")}
    return {"unique_visitors": visitors, **result, "unique_visitors_exact": exact}


def overview(start, end):
    horizon = purged_before()
    length = (end - start).days + 1
    prev_end, prev_start = start - timedelta(days=1), start - timedelta(days=length)
    current, previous = totals(start, end, horizon), totals(prev_start, prev_end, horizon)
    return {
        "range": range_info(start, end),
        "previous_range": range_info(prev_start, prev_end),
        "current": current,
        "previous": previous,
        "change": {k: _pct(current[k], previous[k]) for k in KPI_FIELDS},
    }


# ---------------------------------------------------------------- time series
def series(start, end, granularity):
    """Gap-free points: one per day / week (Monday) / month. Weeks and months are whole periods, so the first one starts
    on or before `start`. Missing days come back as zeros."""
    zero = {k: 0 for k in KPI_FIELDS}
    if granularity == "day":
        rows = {r["date"]: r for r in DailyAnalytics.objects.filter(date__range=(start, end)).values("date", *KPI_FIELDS)}
        points = [{"date": d.isoformat(), **{k: rows.get(d, zero)[k] for k in KPI_FIELDS}} for d in daterange(start, end)]
        return {"granularity": granularity, "range": range_info(start, end), "points": points}

    starts = sorted({period_start(granularity, d) for d in daterange(start, end)})
    first, last = starts[0], period_end(granularity, starts[-1]) - timedelta(days=1)
    periods = {
        r["start_date"]: r
        for r in PeriodAnalytics.objects.filter(period=granularity, start_date__in=starts).values(
            "start_date", "unique_visitors", "page_views", "story_views"
        )
    }
    daily = list(DailyAnalytics.objects.filter(date__range=(first, last)).values("date", "registered_users", "likes", "comments"))
    points = []
    for s in starts:
        e = period_end(granularity, s)
        within = [r for r in daily if s <= r["date"] < e]
        p = periods.get(s, zero)
        points.append(
            {
                "date": s.isoformat(),
                "unique_visitors": p["unique_visitors"] if s in periods else 0,
                "page_views": p["page_views"] if s in periods else 0,
                "story_views": p["story_views"] if s in periods else 0,
                "registered_users": sum(r["registered_users"] for r in within),
                "likes": sum(r["likes"] for r in within),
                "comments": sum(r["comments"] for r in within),
            }
        )
    return {"granularity": granularity, "range": range_info(first, end), "points": points}


# ---------------------------------------------------------------- top stories
def top_stories(start, end, limit):
    horizon = purged_before()
    rows = list(
        DailyStoryStats.objects.filter(date__range=(start, end), story__published_at__isnull=False)
        .values("story_id", "story__title", "story__slug")
        .annotate(views=Sum("views"), daily_uniques=Sum("unique_visitors"))
        .order_by("-views", "-daily_uniques", "story_id")[:limit]
    )
    ids = [r["story_id"] for r in rows]
    lo, hi = utc_start(start), utc_start(end + timedelta(days=1))
    exact = {}
    if horizon is None or start >= horizon:  # distinct visitors per story are only exact while raw events exist
        exact = {
            r["story_id"]: r["n"]
            for r in PageViewEvent.objects.filter(story_id__in=ids, created_at__gte=lo, created_at__lt=hi)
            .values("story_id").annotate(n=Count("visitor_id", distinct=True))
        }
    likes = {
        r["story_id"]: r["n"]
        for r in Like.objects.filter(story_id__in=ids, created_at__gte=lo, created_at__lt=hi).values("story_id").annotate(n=Count("id"))
    }
    comments = {
        r["story_id"]: r["n"]
        for r in Comment.objects.filter(
            story_id__in=ids, status=Comment.Status.APPROVED, created_at__gte=lo, created_at__lt=hi
        ).values("story_id").annotate(n=Count("id"))
    }
    return {
        "range": range_info(start, end),
        "stories": [
            {
                "id": r["story_id"],
                "title": r["story__title"],
                "slug": r["story__slug"],
                "views": r["views"],
                "unique_visitors": exact.get(r["story_id"], r["daily_uniques"]) if exact else r["daily_uniques"],
                "likes": likes.get(r["story_id"], 0),
                "comments": comments.get(r["story_id"], 0),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------- traffic
def traffic(start, end):
    """Top referrer domains and the device split, from the raw events (so only inside the retention window)."""
    events = events_between(start, end + timedelta(days=1))
    referrers = (
        events.values("referrer_domain")
        .annotate(page_views=Count("id"), visitors=Count("visitor_id", distinct=True))
        .order_by("-page_views", "referrer_domain")[:10]
    )
    devices = {r["user_agent_category"]: r["n"] for r in events.values("user_agent_category").annotate(n=Count("id"))}
    return {
        "range": range_info(start, end),
        "referrers": [
            {"domain": r["referrer_domain"] or "Direct", "page_views": r["page_views"], "visitors": r["visitors"]}
            for r in referrers
        ],
        "devices": [{"device": d, "page_views": devices.get(d, 0)} for d in DEVICES],
    }


def granularity_param(params):
    value = params.get("granularity") or "day"
    if value not in ("day", "week", "month"):
        raise _bad("granularity", "granularity must be day, week or month.")
    return value


def top_limit(params):
    return _int(params, "limit", 10, 1, TOP_STORIES_MAX)

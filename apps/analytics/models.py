"""Analytics tables. Nothing here can identify a person: ids are hashed, IPs and user agents are never stored."""
from django.db import models
from django.utils import timezone


class Visitor(models.Model):
    """One browser, identified only by an HMAC hash of the random id it keeps in localStorage."""

    visitor_key_hash = models.CharField(max_length=64, unique=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return f"Visitor {self.pk}"


class PageViewEvent(models.Model):
    """One counted page view. Raw rows are deleted after ANALYTICS_RETENTION_DAYS; the aggregates stay."""

    class Device(models.TextChoices):
        DESKTOP = "desktop", "Desktop"
        MOBILE = "mobile", "Mobile"
        TABLET = "tablet", "Tablet"
        OTHER = "other", "Other"  # bots are dropped before they are stored, so there is no "bot" row

    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name="events")
    story = models.ForeignKey("stories.Story", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    path = models.CharField(max_length=300)  # public path without query string, e.g. /stories/my-story
    session_key_hash = models.CharField(max_length=64)
    referrer_domain = models.CharField(max_length=100, blank=True)  # domain only, never a URL
    user_agent_category = models.CharField(max_length=10, choices=Device.choices, default=Device.OTHER)
    created_at = models.DateTimeField(default=timezone.now)  # default (not auto_now_add) so tests can backdate

    class Meta:
        indexes = [
            models.Index(fields=["created_at"], name="pv_created_idx"),
            models.Index(fields=["story", "created_at"], name="pv_story_created_idx"),
            models.Index(fields=["visitor", "created_at"], name="pv_visitor_created_idx"),
        ]


class DailyAnalytics(models.Model):
    """Totals for one UTC day."""

    date = models.DateField(unique=True)
    unique_visitors = models.PositiveIntegerField(default=0)
    page_views = models.PositiveIntegerField(default=0)
    story_views = models.PositiveIntegerField(default=0)
    registered_users = models.PositiveIntegerField(default=0)  # new accounts created that day
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)  # approved comments created that day
    updated_at = models.DateTimeField(auto_now=True)


class PeriodAnalytics(models.Model):
    """Totals for one UTC week (starting Monday) or month. unique_visitors is EXACT (distinct visitors in the period)."""

    class Period(models.TextChoices):
        WEEK = "week", "Week"
        MONTH = "month", "Month"

    period = models.CharField(max_length=5, choices=Period.choices)
    start_date = models.DateField()
    unique_visitors = models.PositiveIntegerField(default=0)
    page_views = models.PositiveIntegerField(default=0)
    story_views = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["period", "start_date"], name="period_unique_start")]


class DailyStoryStats(models.Model):
    """Views of one story on one UTC day (feeds Top stories)."""

    date = models.DateField()
    story = models.ForeignKey("stories.Story", on_delete=models.CASCADE, related_name="+")
    views = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["date", "story"], name="storystats_unique_date_story")]


class AnalyticsState(models.Model):
    """Tiny key/value table. Used for `purged_before`: raw events older than this date no longer exist."""

    key = models.CharField(max_length=40, unique=True)
    value = models.CharField(max_length=100, blank=True)

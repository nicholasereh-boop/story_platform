"""Staff-only analytics API under /api/v1/admin/analytics/. Everything here returns aggregates only."""
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsStaffUser

from . import reports
from .aggregation import ensure_fresh


class AdminAnalyticsView(APIView):
    """Shared behaviour: staff only, parse the range, and refresh today's numbers when the range includes today."""

    permission_classes = [IsStaffUser]
    http_method_names = ["get", "head", "options"]

    def get(self, request, *args, **kwargs):
        today = timezone.now().date()
        start, end = reports.parse_range(request.query_params, today)
        extra = self.parse_extra(request.query_params)  # validate everything BEFORE doing any work
        if end >= today:
            ensure_fresh()
        return Response(self.build(start, end, extra))

    def parse_extra(self, params):
        return None


class OverviewView(AdminAnalyticsView):
    def build(self, start, end, extra):
        return reports.overview(start, end)


class DailyView(AdminAnalyticsView):
    """?granularity=day|week|month (default day)."""

    def parse_extra(self, params):
        return reports.granularity_param(params)

    def build(self, start, end, granularity):
        return reports.series(start, end, granularity)


class StoriesView(AdminAnalyticsView):
    """Top stories by views. ?limit= up to 50 (default 10)."""

    def parse_extra(self, params):
        return reports.top_limit(params)

    def build(self, start, end, limit):
        return reports.top_stories(start, end, limit)


class TrafficView(AdminAnalyticsView):
    def build(self, start, end, extra):
        return reports.traffic(start, end)

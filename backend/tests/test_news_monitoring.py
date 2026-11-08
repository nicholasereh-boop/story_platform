"""News Phase 6: the monitoring snapshot, its alerts, the management command and the hourly task."""
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.news.models import NewsIngestionRun, NewsSource, NewsTakedown
from apps.news.services import articles, monitoring
from apps.news.tasks import monitor

from .marketplace_helpers import client_for
from .news_helpers import ADMIN, make_article, make_live_article, make_record, make_source

pytestmark = pytest.mark.django_db


def codes(snap):
    return [a["code"] for a in monitoring.alerts(snap)]


def test_a_quiet_newsroom_has_no_alerts():
    assert monitoring.alerts(monitoring.snapshot()) == []


def test_quarantined_articles_and_old_complaints_raise_alerts(staff):
    source = make_source()
    make_record(source)
    live = make_live_article(source, staff)
    t = NewsTakedown.objects.create(article=live, contact_name="Pat", contact_email="p@example.com", message="x" * 20)
    NewsTakedown.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(hours=30))
    articles.quarantine(live, "test", staff)
    found = codes(monitoring.snapshot())
    assert "quarantined" in found and "complaint_overdue" in found


def test_overdue_scheduled_articles_are_an_error(staff):
    source = make_source()
    make_record(source)
    article = make_article(source, staff)
    article.status = "scheduled"
    article.scheduled_for = timezone.now() - timedelta(minutes=30)
    article.save()
    problems = monitoring.alerts(monitoring.snapshot())
    assert [p["level"] for p in problems if p["code"] == "scheduled_overdue"] == ["error"]


def test_rights_ending_soon_is_a_warning_and_far_future_is_not(settings):
    settings.NEWS_RIGHTS_WARNING_DAYS = 14
    soon, later = make_source("soon"), make_source("later")
    make_record(soon, effective_until=timezone.now() + timedelta(days=5))
    make_record(later, effective_until=timezone.now() + timedelta(days=60))
    snap = monitoring.snapshot()
    assert [r["source"] for r in snap["rights_ending_soon"]] == ["Daily Example"] and snap["rights_ending_soon"][0]["title"]
    assert codes(snap) == ["rights_ending"]


def test_failing_and_stale_feeds_are_reported_only_when_importing_is_on(settings):
    source = make_source(adapter="rss", feed_url="https://example.com/feed.xml")
    started = timezone.now() - timedelta(hours=10)
    NewsSource.objects.filter(pk=source.pk).update(created_at=started)  # added long ago and never polled successfully
    for i in range(3):
        NewsIngestionRun.objects.create(source=source, status="failed", reason="http_error", started_at=started + timedelta(minutes=i))
    settings.NEWS_IMPORT_ENABLED = False
    assert monitoring.snapshot()["failing_sources"] == []
    settings.NEWS_IMPORT_ENABLED = True
    snap = monitoring.snapshot()
    assert snap["failing_sources"][0]["failure_streak"] == 3 and snap["stale_sources"]
    assert {"feed_failing", "feed_stale"} <= set(codes(snap))


def test_staff_endpoint_and_permissions(client, user, staff):
    assert client.get(ADMIN + "monitoring/").status_code in (401, 403)
    assert client_for(user).get(ADMIN + "monitoring/").status_code == 403
    data = client_for(staff).get(ADMIN + "monitoring/").json()["data"]
    assert data["alerts"] == [] and data["articles"]["published"] == 0


def test_command_prints_and_exits_nonzero_only_for_errors(staff):
    out = StringIO()
    call_command("news_health", stdout=out)
    assert "All good." in out.getvalue()
    source = make_source()
    make_record(source)
    article = make_article(source, staff)
    article.status, article.scheduled_for = "scheduled", timezone.now() - timedelta(hours=1)
    article.save()
    with pytest.raises(SystemExit) as stop:
        call_command("news_health", stdout=StringIO())
    assert stop.value.code == 1


def test_hourly_task_logs_one_line_per_problem(caplog, staff):
    source = make_source()
    make_record(source, effective_until=timezone.now() + timedelta(days=3))
    with caplog.at_level("WARNING", logger="apps.news.monitoring"):
        assert monitor() == 1
    assert "rights_ending" in caplog.text
    
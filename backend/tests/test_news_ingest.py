"""News Phase 4: safe fetching, feed parsing, scheduled and manual imports, quotas and backoff, and the review queue default."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.news.models import NewsArticle, NewsIngestionRun
from apps.news.providers import AdapterError
from apps.news.providers.rss import RssAdapter
from apps.news.services import ingest, netguard

from .marketplace_helpers import client_for
from .news_helpers import ADMIN, make_record, make_source

pytestmark = pytest.mark.django_db
FEED = "https://feeds.example.com/rss"
OK_HOST = lambda host: None  # noqa: E731  (a resolver that accepts any host: no real DNS in tests)

RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>Wire</title><language>en</language>
<item><guid>id-1</guid><title>First story</title><link>https://feeds.example.com/a/1</link><description>&lt;b&gt;Summary&lt;/b&gt; one</description>
<content:encoded><![CDATA[<p>Full text one.</p><script>bad()</script>]]></content:encoded><dc:creator>Ada</dc:creator><pubDate>Tue, 03 Nov 2026 09:00:00 GMT</pubDate></item>
<item><guid>id-2</guid><title>Second story</title><link>https://feeds.example.com/a/2</link><description>Only a summary</description></item>
<item><guid>id-3</guid><title>Third story</title><link>http://insecure.example.com/3</link><content:encoded><![CDATA[<p>Third text.</p>]]></content:encoded></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en"><title>T</title>
<entry><id>tag:a,1</id><title>Atom one</title><link rel="alternate" href="https://feeds.example.com/at/1"/><summary>Sum</summary>
<content type="html">&lt;p&gt;Atom body&lt;/p&gt;</content><author><name>Bo</name></author><published>2026-11-03T09:00:00Z</published></entry></feed>"""


class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


class FakeSession:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kwargs):
        self.calls.append(url)
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        return item


def rss_session(body=RSS):
    return FakeSession(FakeResponse(200, body))


@pytest.fixture
def importing(settings):
    settings.NEWS_IMPORT_ENABLED = True


def feed_source(**overrides):
    values = {"adapter": "rss", "feed_url": FEED, "source_type": "licensed", "poll_interval_minutes": 15}
    values.update(overrides)
    source = make_source("wire", name="Wire", **values)
    make_record(source)
    return source


# ---- netguard -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("ip,expected", [("8.8.8.8", True), ("10.0.0.5", False), ("127.0.0.1", False), ("169.254.169.254", False), ("192.168.1.1", False), ("::1", False), ("::ffff:10.0.0.1", False), ("nonsense", False)])
def test_is_public_ip(ip, expected):
    assert netguard.is_public_ip(ip) is expected


@pytest.mark.parametrize("url", ["http://feeds.example.com/rss", "https://feeds.example.com:8443/rss", "https://user:pw@feeds.example.com/rss", "https://evil.example.net/rss", "https://feeds.example.com.evil.net/rss", "file:///etc/passwd"])
def test_check_target_rejects_unsafe_addresses(url):
    with pytest.raises(netguard.UnsafeTarget):
        netguard.check_target(url, ["feeds.example.com"], OK_HOST)


def test_private_resolution_is_rejected():
    def resolver(host):
        raise netguard.UnsafeTarget("private")

    with pytest.raises(netguard.FetchFailed) as exc:
        netguard.fetch_bytes(FEED, allowed_hosts=["feeds.example.com"], max_bytes=1000, session=rss_session(), resolver=resolver)
    assert exc.value.code == "unsafe_target"


def test_redirect_to_another_host_is_refused():
    session = FakeSession(FakeResponse(302, headers={"Location": "https://evil.example.net/x"}))
    with pytest.raises(netguard.FetchFailed) as exc:
        netguard.fetch_bytes(FEED, allowed_hosts=["feeds.example.com"], max_bytes=1000, session=session, resolver=OK_HOST)
    assert exc.value.code == "unsafe_target" and session.calls == [FEED]


def test_redirect_on_the_same_host_is_followed():
    session = FakeSession(FakeResponse(301, headers={"Location": "/new.xml"}), FakeResponse(200, b"<x/>"))
    body, status = netguard.fetch_bytes(FEED, allowed_hosts=["feeds.example.com"], max_bytes=1000, session=session, resolver=OK_HOST)
    assert body == b"<x/>" and session.calls[-1] == "https://feeds.example.com/new.xml"


def test_redirect_loop_is_cut_off():
    session = FakeSession(FakeResponse(302, headers={"Location": "/again"}))
    with pytest.raises(netguard.FetchFailed) as exc:
        netguard.fetch_bytes(FEED, allowed_hosts=["feeds.example.com"], max_bytes=1000, session=session, resolver=OK_HOST)
    assert exc.value.code == "redirects"


def test_size_limit_is_enforced_by_header_and_by_stream():
    with pytest.raises(netguard.FetchFailed) as exc:
        netguard.fetch_bytes(FEED, allowed_hosts=["feeds.example.com"], max_bytes=10, session=FakeSession(FakeResponse(200, b"x" * 5, {"Content-Length": "999"})), resolver=OK_HOST)
    assert exc.value.code == "too_large"
    with pytest.raises(netguard.FetchFailed) as exc:
        netguard.fetch_bytes(FEED, allowed_hosts=["feeds.example.com"], max_bytes=10, session=FakeSession(FakeResponse(200, b"x" * 50)), resolver=OK_HOST)
    assert exc.value.code == "too_large"


def test_server_errors_are_retryable_and_client_errors_are_not():
    with pytest.raises(netguard.FetchFailed) as exc:
        netguard.fetch_bytes(FEED, allowed_hosts=["feeds.example.com"], max_bytes=10, session=FakeSession(FakeResponse(503)), resolver=OK_HOST)
    assert exc.value.retryable and exc.value.http_status == 503
    with pytest.raises(netguard.FetchFailed) as exc:
        netguard.fetch_bytes(FEED, allowed_hosts=["feeds.example.com"], max_bytes=10, session=FakeSession(FakeResponse(404)), resolver=OK_HOST)
    assert not exc.value.retryable


def test_network_errors_are_retryable():
    import requests

    with pytest.raises(netguard.FetchFailed) as exc:
        netguard.fetch_bytes(FEED, allowed_hosts=["feeds.example.com"], max_bytes=10, session=FakeSession(requests.ConnectionError()), resolver=OK_HOST)
    assert exc.value.retryable


# ---- parsing ------------------------------------------------------------------------------------------
def test_rss_parsing():
    items = RssAdapter().parse(RSS, None)
    assert [i.external_id for i in items] == ["id-1", "id-2", "id-3"]
    first = items[0]
    assert first.title == "First story" and first.standfirst == "Summary one" and "Full text one." in first.body and first.author == "Ada"
    assert first.published_at.year == 2026 and first.language == "en"
    assert items[1].body == ""  # summary only: no full text is invented
    assert items[2].canonical_url == ""  # a non-https link is not kept


def test_atom_parsing():
    (item,) = RssAdapter().parse(ATOM, None)
    assert item.title == "Atom one" and item.canonical_url == "https://feeds.example.com/at/1" and item.author == "Bo" and item.body == "<p>Atom body</p>"


@pytest.mark.parametrize("payload", [b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel/></rss>', b"not xml at all", b"<html><body/></html>"])
def test_bad_feeds_are_refused(payload):
    with pytest.raises(AdapterError):
        RssAdapter().parse(payload, None)


# ---- scheduled import ---------------------------------------------------------------------------------
def test_nothing_is_fetched_while_imports_are_off(settings):
    settings.NEWS_IMPORT_ENABLED = False
    session = rss_session()
    run = ingest.run_source(feed_source(), session=session, resolver=OK_HOST)
    assert run.status == "skipped" and run.reason == "imports_disabled" and session.calls == []


def test_import_creates_pending_articles_with_full_text_only(importing):
    source = feed_source()
    run = ingest.run_source(source, session=rss_session(), resolver=OK_HOST)
    assert run.status == "ok" and run.fetched == 3 and run.created == 3
    by_id = {a.external_id: a for a in NewsArticle.objects.all()}
    assert by_id["id-1"].status == "pending" and by_id["id-1"].imported and "script" not in by_id["id-1"].body
    assert by_id["id-2"].status == "draft" and by_id["id-2"].body == ""  # no full text in the feed: stays out of the review queue
    assert not any(a.status in ("published", "scheduled") for a in by_id.values())  # imports are never live


def test_second_poll_adds_no_duplicates(importing):
    source = feed_source()
    ingest.run_source(source, session=rss_session(), resolver=OK_HOST)
    run = ingest.run_source(source, session=rss_session(), resolver=OK_HOST, force=True)
    assert run.created == 0 and run.duplicates == 3 and NewsArticle.objects.count() == 3


def test_item_cap(importing):
    source = feed_source(max_items_per_poll=1)
    run = ingest.run_source(source, session=rss_session(), resolver=OK_HOST)
    assert run.fetched == 3 and run.created == 1


def test_poll_interval_quota_and_backoff(importing):
    source = feed_source(poll_interval_minutes=60, daily_request_quota=3)
    now = timezone.now()
    assert ingest.run_source(source, now=now, session=rss_session(), resolver=OK_HOST).status == "ok"
    assert ingest.run_source(source, now=now + timedelta(minutes=5), session=rss_session(), resolver=OK_HOST).reason == "too_soon"
    assert ingest.run_source(source, now=now + timedelta(minutes=61), session=rss_session(), resolver=OK_HOST).status == "ok"
    assert ingest.run_source(source, now=now + timedelta(minutes=125), session=rss_session(), resolver=OK_HOST).status == "ok"
    assert ingest.run_source(source, now=now + timedelta(minutes=300), session=rss_session(), resolver=OK_HOST).reason == "daily_quota_reached"


def test_failures_are_recorded_and_back_the_source_off(importing):
    source = feed_source(poll_interval_minutes=15, daily_request_quota=50)
    now = timezone.now()
    run = ingest.run_source(source, now=now, session=FakeSession(FakeResponse(503)), resolver=OK_HOST)
    assert run.status == "failed" and run.retryable and run.http_status == 503
    # after one failure the wait doubles (30 minutes), so 20 minutes later it is still backing off
    assert ingest.run_source(source, now=now + timedelta(minutes=20), session=rss_session(), resolver=OK_HOST).reason == "backing_off"
    assert ingest.run_source(source, now=now + timedelta(minutes=31), session=rss_session(), resolver=OK_HOST).status == "ok"
    assert ingest.health(source)["failure_streak"] == 0


def test_bad_feed_is_a_failed_run_not_a_crash(importing):
    run = ingest.run_source(feed_source(), session=rss_session(b"garbage"), resolver=OK_HOST)
    assert run.status == "failed" and run.reason == "bad_feed" and not run.retryable


def test_unapproved_sources_and_missing_rights_are_never_polled(importing):
    session = rss_session()
    pending = make_source("p", name="P", adapter="rss", feed_url=FEED, approval_state="pending")
    make_record(pending)
    assert ingest.run_source(pending, session=session, resolver=OK_HOST).reason.startswith("rights:")
    no_record = make_source("n", name="N", adapter="rss", feed_url=FEED)
    assert ingest.run_source(no_record, session=session, resolver=OK_HOST).reason == "rights:no_rights_record"
    assert session.calls == []


def test_metadata_only_and_text_less_sources_are_not_imported(importing):
    meta = make_source("m", name="M", adapter="rss", feed_url=FEED, source_type="metadata_only")
    make_record(meta)
    assert ingest.run_source(meta, session=rss_session(), resolver=OK_HOST).reason == "metadata_only_source"
    nofull = make_source("f", name="F", adapter="rss", feed_url=FEED, allows_full_text=False)
    make_record(nofull)
    assert ingest.run_source(nofull, session=rss_session(), resolver=OK_HOST).reason == "full_text_not_permitted"


def test_denylisted_publisher_is_not_polled_without_written_permission(importing):
    source = make_source("bbc", name="BBC", adapter="rss", feed_url="https://feeds.bbci.co.uk/news/rss.xml", website_url="https://www.bbc.co.uk")
    make_record(source, basis="open_licence")  # an approved record with the wrong basis (bypassing approve_record)
    run = ingest.run_source(source, session=rss_session(), resolver=OK_HOST)
    assert run.reason == "publisher_needs_written_permission"


def test_upstream_change_updates_unpublished_items_and_leaves_live_ones(importing, staff):
    source = feed_source()
    ingest.run_source(source, session=rss_session(), resolver=OK_HOST)
    changed = RSS.replace(b"Full text one.", b"Full text one, corrected.")
    run = ingest.run_source(source, session=rss_session(changed), resolver=OK_HOST, force=True)
    assert run.updated == 1 and "corrected" in NewsArticle.objects.get(external_id="id-1").body
    from apps.news.services import articles

    article = NewsArticle.objects.get(external_id="id-1")
    articles.publish(article, staff)
    again = RSS.replace(b"Full text one.", b"Full text one, corrected twice.")
    run = ingest.run_source(source, session=rss_session(again), resolver=OK_HOST, force=True)
    assert run.changed_live == 1 and "twice" not in NewsArticle.objects.get(external_id="id-1").body


def test_every_run_is_recorded_including_skips(importing, settings):
    source = feed_source()
    ingest.run_source(source, session=rss_session(), resolver=OK_HOST)
    settings.NEWS_IMPORT_ENABLED = False
    ingest.run_source(source, session=rss_session(), resolver=OK_HOST)
    assert list(NewsIngestionRun.objects.order_by("id").values_list("status", flat=True)) == ["ok", "skipped"]


# ---- manual import API --------------------------------------------------------------------------------
def manual_payload(source, **extra):
    return {"source": source.pk, "title": "Pasted article", "body": "<p>Permitted text.</p><script>x()</script>", "canonical_url": "https://example.com/pasted", "author_name": "Cy", **extra}


def test_preview_saves_nothing_and_reports_blockers(staff):
    source = make_source()
    r = client_for(staff).post(ADMIN + "articles/import-preview/", manual_payload(source), format="json")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "script" not in data["body"] and data["can_publish"] is False and "no_rights_record" in data["blockers"]
    assert NewsArticle.objects.count() == 0


def test_preview_flags_duplicates(staff):
    source = make_source()
    make_record(source)
    c = client_for(staff)
    assert c.post(ADMIN + "articles/import/", manual_payload(source), format="json").status_code == 201
    data = c.post(ADMIN + "articles/import-preview/", manual_payload(source), format="json").json()["data"]
    assert data["duplicate"]["matched_by"] == "canonical_url"


def test_manual_import_goes_to_the_review_queue_and_refuses_duplicates(staff):
    from apps.audit.models import AuditLog

    source = make_source()
    make_record(source)
    c = client_for(staff)
    r = c.post(ADMIN + "articles/import/", manual_payload(source), format="json")
    assert r.status_code == 201, r.content
    assert r.json()["data"]["status"] == "pending" and r.json()["data"]["imported"] is True
    assert c.post(ADMIN + "articles/import/", manual_payload(source), format="json").status_code == 400
    assert AuditLog.objects.filter(action="news.article_import").count() == 1


def test_import_endpoints_are_staff_only(client, user):
    source = make_source()
    assert client.post(ADMIN + "articles/import/", manual_payload(source), format="json").status_code in (401, 403)
    assert client_for(user).post(ADMIN + "articles/import-preview/", manual_payload(source), format="json").status_code == 403
    assert client_for(user).get(ADMIN + "ingestion/").status_code == 403


def test_poll_now_and_ingestion_health_endpoints(staff, importing, monkeypatch):
    source = feed_source()
    monkeypatch.setattr(netguard, "fetch_bytes", lambda *a, **k: (RSS, 200))
    c = client_for(staff)
    r = c.post(ADMIN + f"sources/{source.pk}/poll/")
    assert r.status_code == 200 and r.json()["data"]["created"] == 3
    runs = c.get(ADMIN + "ingestion/").json()
    assert runs["data"][0]["status"] == "ok" and runs["pagination"]["count"] == 1
    health = c.get(ADMIN + "ingestion/health/").json()["data"]
    assert health[0]["name"] == "Wire" and health[0]["last_status"] == "ok" and health[0]["runs_today"] == 1


# ---- tasks --------------------------------------------------------------------------------------------
def test_scheduler_does_nothing_while_imports_are_off(settings):
    from apps.news import tasks

    settings.NEWS_IMPORT_ENABLED = False
    feed_source()
    assert tasks.poll_due_sources() == 0


def test_scheduler_queues_only_approved_active_sources_with_adapters(importing, monkeypatch):
    from apps.news import tasks

    good = feed_source()
    make_source("manual", name="Manual only")
    make_source("paused", name="Paused", adapter="rss", feed_url=FEED, is_active=False)
    queued = []
    monkeypatch.setattr(tasks.poll_source, "delay", lambda source_id: queued.append(source_id))
    assert tasks.poll_due_sources() == 1 and queued == [good.pk]


def test_maintenance_tasks_run(staff):
    from apps.news import tasks

    assert tasks.publish_scheduled() == 0
    assert tasks.rights_maintenance() == 0
"""News Phase 3: article life cycle, the publishing gate, quarantine, the sanitizer and the public API."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.news.models import NewsArticle, NewsAsset, NewsCategory
from apps.news.services import articles, policy, rights, sanitize
from apps.news.services.articles import ArticleError

from .marketplace_helpers import client_for
from .news_helpers import ADMIN, API, make_article, make_live_article, make_record, make_source

pytestmark = pytest.mark.django_db


@pytest.fixture
def public(settings):
    settings.NEWS_PUBLIC_ENABLED = True


# ---- sanitizer ---------------------------------------------------------------------------------
def test_sanitizer_removes_scripts_handlers_and_unsafe_links():
    html = '<p onclick="x()">Hi <script>alert(1)</script><a href="javascript:alert(1)">bad</a> <a href="https://ok.example/a" onmouseover="y()">good</a><iframe src="https://e"></iframe><img src=x onerror=z()></p>'
    out = sanitize.clean_body(html)
    assert "<script" not in out and "alert(1)" not in out and "onclick" not in out and "onmouseover" not in out
    assert "javascript:" not in out and "<iframe" not in out and "<img" not in out
    assert 'href="https://ok.example/a"' in out and "nofollow" in out and "noopener" in out


def test_sanitizer_keeps_basic_formatting():
    out = sanitize.clean_body("<h2>Title</h2><p><strong>Bold</strong> and <em>it</em></p><ul><li>one</li></ul><blockquote>q</blockquote>")
    assert "<h2>" in out and "<strong>" in out and "<li>" in out and "<blockquote>" in out


def test_content_hash_ignores_markup_and_case():
    assert sanitize.content_hash("A Title", "<p>Same  text</p>") == sanitize.content_hash("a title", "<div>same text</div>")


def test_url_normalisation_drops_tracking_and_fragments():
    assert sanitize.url_hash("https://Example.com/a/?utm_source=x#top") == sanitize.url_hash("https://example.com/a")


def test_denylisted_hosts():
    assert policy.is_denylisted("https://www.bbc.co.uk/news/1") and policy.is_denylisted("https://edition.cnn.com/x")
    assert not policy.is_denylisted("https://theconversation.com/x")


# ---- creating and the gate --------------------------------------------------------------------------
def test_create_sanitises_and_records_revision_and_attribution(staff):
    source = make_source(attribution_template="By {author} for {source}")
    make_record(source)
    a = make_article(source, staff, data={"body": '<p>Hello</p><script>bad()</script>'})
    assert "script" not in a.body and a.status == "draft" and a.slug
    assert a.attribution == "By Ada Obi for Daily Example"
    assert a.rights_record_id and a.revisions.count() == 1 and a.revisions.first().action == "created"


def test_slugs_are_unique(staff):
    source = make_source()
    make_record(source)
    assert make_article(source, staff).slug != make_article(source, staff).slug


def test_full_flow_publishes(staff):
    source = make_source()
    make_record(source)
    a = make_article(source, staff)
    articles.submit(a, staff)
    assert a.status == "pending"
    articles.publish(a, staff)
    assert a.status == "published" and a.published_at and a.reviewer == staff
    assert [r.action for r in a.revisions.order_by("number")] == ["created", "submitted", "published"]


def _blockers(article):
    ok, reasons = articles.check_publishable(article)
    assert not ok
    return reasons


def test_gate_refuses_without_a_rights_record(staff):
    assert "no_rights_record" in _blockers(make_article(make_source(), staff))


def test_gate_refuses_unapproved_source(staff):
    source = make_source(approval_state="pending")
    make_record(source)
    assert "source_not_approved" in _blockers(make_article(source, staff))


def test_gate_refuses_without_commercial_rights(staff):
    source = make_source(allows_commercial_use=False)
    make_record(source)
    assert "commercial_use_not_permitted" in _blockers(make_article(source, staff))


def test_commercial_requirement_can_be_relaxed_by_setting(staff, settings):
    settings.NEWS_REQUIRE_COMMERCIAL_RIGHTS = False
    source = make_source(allows_commercial_use=False)
    make_record(source, allows_commercial_use=False)
    assert articles.check_publishable(make_article(source, staff))[0]


def test_gate_refuses_full_text_when_not_permitted(staff):
    source = make_source(allows_full_text=False)
    make_record(source)
    assert "full_text_not_permitted" in _blockers(make_article(source, staff))


def test_gate_requires_attribution_and_body(staff):
    source = make_source()
    make_record(source)
    a = make_article(source, staff)
    a.attribution = ""
    assert "attribution_missing" in _blockers(a)
    b = make_article(source, staff, data={"body": ""})
    assert "body_missing" in _blockers(b)


def test_metadata_only_article_never_publishes(staff):
    source = make_source(source_type="metadata_only")
    make_record(source)
    reasons = _blockers(make_article(source, staff))
    assert "metadata_only_source" in reasons or "metadata_only_article" in reasons


def test_no_derivatives_licence_blocks_edits_of_imported_text(staff):
    source = make_source(source_type="open_licensed")
    make_record(source, allows_modification=False)
    a = make_article(source, staff, imported=True, external_id="x1", data={"canonical_url": "https://example.com/x1"})
    assert articles.check_publishable(a)[0]
    articles.update_article(a, staff, {"body": "<p>I rewrote this.</p>"})
    assert "edits_not_permitted" in _blockers(a)


def test_imported_article_needs_a_link_back(staff):
    source = make_source(source_type="licensed")
    make_record(source)
    a = make_article(source, staff, imported=True, external_id="x2", data={"original_url": "", "canonical_url": ""})
    assert "original_link_missing" in _blockers(a)


def test_publish_error_lists_reasons(staff):
    a = make_article(make_source(), staff)
    with pytest.raises(ArticleError) as exc:
        articles.publish(a, staff)
    assert "no_rights_record" in exc.value.reasons


def test_editing_a_live_article_is_rechecked(staff):
    source = make_source()
    make_record(source)
    a = make_live_article(source, staff)
    with pytest.raises(ArticleError):
        articles.update_article(a, staff, {"body": ""})
    articles.update_article(a, staff, {"standfirst": "Fixed typo"}, note="typo")
    assert a.revisions.filter(action="edited").exists()


def test_reject_and_withdraw_need_reasons(staff):
    source = make_source()
    make_record(source)
    a = make_article(source, staff)
    articles.submit(a, staff)
    with pytest.raises(ArticleError):
        articles.reject(a, staff, " ")
    articles.reject(a, staff, "Needs a source link")
    assert a.status == "rejected"
    articles.submit(a, staff)
    articles.publish(a, staff)
    with pytest.raises(ArticleError):
        articles.withdraw(a, staff, "")
    articles.withdraw(a, staff, "Factual error")
    assert a.status == "withdrawn"


def test_duplicate_detection():
    source = make_source()
    make_record(source)
    a = make_article(source, None, imported=True, external_id="abc", data={"canonical_url": "https://example.com/a?utm_source=x"})
    assert articles.find_duplicate(source, external_id="abc")[1] == "external_id"
    assert articles.find_duplicate(source, canonical_url="https://example.com/a")[1] == "canonical_url"
    assert articles.find_duplicate(source, title=a.title, body=a.body)[1] == "content"
    assert articles.find_duplicate(source, title="Other", body="<p>nothing</p>")[0] is None


def test_provider_id_is_unique_per_source():
    source = make_source()
    make_record(source)
    make_article(source, None, imported=True, external_id="dup")
    with pytest.raises(ArticleError):
        make_article(source, None, imported=True, external_id="dup")


# ---- scheduling ---------------------------------------------------------------------------------------
def test_scheduled_article_publishes_when_due(staff):
    source = make_source()
    make_record(source)
    a = make_article(source, staff)
    articles.submit(a, staff)
    articles.publish(a, staff, when=timezone.now() + timedelta(hours=2))
    assert a.status == "scheduled" and articles.publish_due() == 0
    assert articles.publish_due(timezone.now() + timedelta(hours=3)) == 1
    a.refresh_from_db()
    assert a.status == "published" and a.published_at


def test_scheduled_article_is_quarantined_if_rights_lapse_before_it_is_due(staff):
    source = make_source()
    record = make_record(source)
    a = make_article(source, staff)
    articles.submit(a, staff)
    articles.publish(a, staff, when=timezone.now() + timedelta(hours=2))
    NewsRecordUpdate = type(record).objects.filter(pk=record.pk)
    NewsRecordUpdate.update(status="revoked")
    articles.publish_due(timezone.now() + timedelta(hours=3))
    a.refresh_from_db()
    assert a.status == "quarantined"


# ---- quarantine ---------------------------------------------------------------------------------------
def test_revoking_rights_quarantines_live_articles(staff):
    source = make_source()
    record = make_record(source)
    a = make_live_article(source, staff)
    rights.revoke_record(record, staff, "Publisher withdrew permission")
    a.refresh_from_db()
    assert a.status == "quarantined" and a.quarantined_from == "published" and "rights_revoked" in a.quarantine_reason


def test_revoking_one_record_quarantines_only_its_articles(staff):
    source = make_source()
    old = make_record(source, title="old", effective_from=timezone.now() - timedelta(days=30))
    a = make_live_article(source, staff)
    NewsArticle.objects.filter(pk=a.pk).update(rights_record=old)  # published under the older record
    new = make_record(source, title="new")
    b = make_live_article(source, staff)
    assert b.rights_record_id == new.pk
    rights.revoke_record(old, staff, "ended")
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.status == "quarantined" and b.status == "published"


def test_suspending_a_source_quarantines_its_articles(staff):
    source = make_source()
    make_record(source)
    a = make_live_article(source, staff)
    rights.suspend_source(source, staff)
    a.refresh_from_db()
    assert a.status == "quarantined"


def test_sweep_quarantines_expired_rights(staff):
    source = make_source()
    record = make_record(source, effective_until=timezone.now() + timedelta(days=1))
    a = make_live_article(source, staff)
    type(record).objects.filter(pk=record.pk).update(effective_until=timezone.now() - timedelta(minutes=1))
    assert articles.sweep_rights() >= 1
    a.refresh_from_db()
    assert a.status == "quarantined"


def test_restore_returns_to_review_not_to_public(staff):
    source = make_source()
    record = make_record(source)
    a = make_live_article(source, staff)
    rights.revoke_record(record, staff, "ended")
    make_record(source, title="renewed")
    a.refresh_from_db()
    articles.restore(a, staff)
    assert a.status == "pending" and a.rights_record.title == "renewed" and a.quarantine_reason == ""


def test_denylisted_publisher_needs_written_permission(staff):
    source = make_source(website_url="https://www.bbc.co.uk")
    record = make_record(source, status="draft", basis="open_licence")
    with pytest.raises(rights.RightsError):
        rights.approve_record(record, staff)
    record.basis = "written_permission"
    rights.approve_record(record, staff)
    assert record.status == "approved"


# ---- public API ---------------------------------------------------------------------------------------
def test_public_api_is_off_until_enabled(client, settings):
    settings.NEWS_PUBLIC_ENABLED = False
    assert client.get(API + "articles/").status_code == 404
    assert client.get(API + "categories/").status_code == 404


def test_public_list_and_detail_show_only_published(client, staff, public):
    source = make_source()
    make_record(source)
    live = make_live_article(source, staff, data={"title": "Live story"})
    make_article(source, staff, data={"title": "Draft story"})
    r = client.get(API + "articles/")
    assert r.status_code == 200
    titles = [a["title"] for a in r.json()["data"]]
    assert titles == ["Live story"]
    detail = client.get(API + f"articles/{live.slug}/")
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert "<p>" in body["body"] and body["attribution"] and body["original_url"] == "https://example.com/original"
    assert "content_hash" not in body and "review_note" not in body and "rights_record" not in body


def test_non_public_article_is_a_404(client, staff, public):
    source = make_source()
    make_record(source)
    draft = make_article(source, staff)
    assert client.get(API + f"articles/{draft.slug}/").status_code == 404


def test_lapsed_rights_hide_an_article_even_before_quarantine_runs(client, staff, public):
    source = make_source()
    record = make_record(source)
    live = make_live_article(source, staff)
    type(record).objects.filter(pk=record.pk).update(status="revoked")  # no handler ran: simulates the gap before the sweep
    assert client.get(API + f"articles/{live.slug}/").status_code == 404
    assert client.get(API + "articles/").json()["data"] == []


def test_suspended_source_articles_are_hidden_at_once(client, staff, public):
    source = make_source()
    make_record(source)
    live = make_live_article(source, staff)
    type(source).objects.filter(pk=source.pk).update(approval_state="suspended")
    assert client.get(API + f"articles/{live.slug}/").status_code == 404


def test_cache_is_cleared_when_an_article_is_published_or_withdrawn(client, staff, public):
    source = make_source()
    make_record(source)
    assert client.get(API + "articles/").json()["data"] == []  # cached empty list
    live = make_live_article(source, staff)
    assert len(client.get(API + "articles/").json()["data"]) == 1
    articles.withdraw(live, staff, "error")
    assert client.get(API + "articles/").json()["data"] == []


def test_filters_and_search(client, staff, public):
    source = make_source()
    make_record(source)
    cat = NewsCategory.objects.create(name="Politics", slug="politics")
    a = make_live_article(source, staff, data={"title": "Bridge vote", "category": cat, "is_featured": True})
    make_live_article(source, staff, data={"title": "Weather today", "body": "<p>Sunny.</p>", "is_breaking": True})
    assert [x["title"] for x in client.get(API + "articles/?category=politics").json()["data"]] == ["Bridge vote"]
    assert [x["title"] for x in client.get(API + "articles/?q=weather").json()["data"]] == ["Weather today"]
    assert client.get(API + "articles/?q=w").json()["data"] == []  # too short
    assert [x["slug"] for x in client.get(API + "featured/").json()["data"]] == [a.slug]
    assert [x["title"] for x in client.get(API + "breaking/").json()["data"]] == ["Weather today"]
    assert [x["slug"] for x in client.get(API + "categories/").json()["data"]] == ["politics"]


def test_related_excludes_the_article_itself(client, staff, public):
    source = make_source()
    make_record(source)
    a = make_live_article(source, staff, data={"title": "One"})
    b = make_live_article(source, staff, data={"title": "Two"})
    assert [x["slug"] for x in client.get(API + f"related/{a.slug}/").json()["data"]] == [b.slug]


def test_search_is_rate_limited(client, staff, public, settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "news_search": "2/min"}}
    codes = [client.get(API + "articles/?q=bridge").status_code for _ in range(4)]
    assert 429 in codes


def test_public_sources_list_has_public_fields_only(client, staff, public):
    make_source(evidence_ref="secret vault id", notes="internal", renewal_contact="legal@x.com")
    data = client.get(API + "sources/").json()["data"]
    assert set(data[0]) == {"name", "slug", "website_url", "source_type"}


def test_only_cleared_unexpired_commercial_assets_are_shown(client, staff, public):
    source = make_source()
    make_record(source)
    a = make_live_article(source, staff)
    common = {"article": a, "kind": "video", "video_id": "dQw4w9WgXcQ", "credit": "Photo: X", "licence": "CC BY", "evidence_url": "https://e.example/1"}
    NewsAsset.objects.create(approval_state="cleared", allows_commercial_use=True, **common)
    NewsAsset.objects.create(approval_state="pending", allows_commercial_use=True, **common)
    NewsAsset.objects.create(approval_state="cleared", allows_commercial_use=False, **common)
    NewsAsset.objects.create(approval_state="cleared", allows_commercial_use=True, expires_at=timezone.now() - timedelta(days=1), **common)
    assert len(client.get(API + f"articles/{a.slug}/").json()["data"]["assets"]) == 1


def test_counter_counts_only_when_the_licence_requires_it(client, staff, public):
    source = make_source()
    make_record(source, requires_counter=True)
    a = make_live_article(source, staff)
    assert client.post(API + f"articles/{a.slug}/view/").json()["data"]["counted"] is True
    client.post(API + f"articles/{a.slug}/view/")
    assert a.view_counts.get().count == 2
    s2 = make_source("other", name="Other")
    make_record(s2)
    b = make_live_article(s2, staff)
    assert client.post(API + f"articles/{b.slug}/view/").json()["data"]["counted"] is False


def test_public_endpoints_are_read_only(client, public):
    assert client.post(API + "articles/", {}, format="json").status_code == 405


# ---- staff API ---------------------------------------------------------------------------------------
def test_newsroom_api_is_staff_only(client, user, staff):
    assert client.get(ADMIN + "articles/").status_code in (401, 403)
    assert client_for(user).get(ADMIN + "articles/").status_code == 403
    assert client_for(staff).get(ADMIN + "articles/").status_code == 200


def test_newsroom_workflow_through_the_api(staff):
    source = make_source()
    make_record(source)
    c = client_for(staff)
    r = c.post(ADMIN + "articles/", {"source": source.pk, "title": "Hello <b>", "body": "<p>Text</p>"}, format="json")
    assert r.status_code == 400  # markup in a plain-text title
    r = c.post(ADMIN + "articles/", {"source": source.pk, "title": "Hello", "body": "<p>Text</p><script>x()</script>", "original_url": "https://example.com/o", "author_name": "Ada"}, format="json")
    assert r.status_code == 201, r.content
    aid = r.json()["data"]["id"]
    assert "script" not in r.json()["data"]["body"]
    assert c.post(ADMIN + f"articles/{aid}/publish/").status_code == 200  # drafts may be published directly by staff when the gate passes
    detail = c.get(ADMIN + f"articles/{aid}/").json()["data"]
    assert detail["status"] == "published" and detail["can_publish"] is True
    assert c.post(ADMIN + f"articles/{aid}/withdraw/", {"reason": ""}, format="json").status_code == 400
    assert c.post(ADMIN + f"articles/{aid}/withdraw/", {"reason": "error"}, format="json").status_code == 200
    assert len(c.get(ADMIN + f"articles/{aid}/revisions/").json()["data"]) >= 3


def test_api_publish_is_refused_with_blockers_when_rights_are_missing(staff):
    source = make_source()
    c = client_for(staff)
    aid = c.post(ADMIN + "articles/", {"source": source.pk, "title": "No rights", "body": "<p>x</p>"}, format="json").json()["data"]["id"]
    r = c.post(ADMIN + f"articles/{aid}/publish/")
    assert r.status_code == 400 and "no_rights_record" in str(r.json())
    assert NewsArticle.objects.get(pk=aid).status == "draft"


def test_asset_clearance_needs_credit_licence_and_evidence(staff):
    source = make_source()
    make_record(source)
    a = make_article(source, staff)
    c = client_for(staff)
    r = c.post(ADMIN + f"articles/{a.pk}/assets/", {"kind": "video", "video_id": "dQw4w9WgXcQ", "allows_commercial_use": True}, format="json")
    assert r.status_code == 201, r.content
    aid = r.json()["data"]["id"]
    assert c.post(ADMIN + f"assets/{aid}/clear/").status_code == 400
    c.patch(ADMIN + f"assets/{aid}/", {"credit": "Video: X", "licence": "CC BY 4.0", "evidence_url": "https://e.example/1"}, format="json")
    assert c.post(ADMIN + f"assets/{aid}/clear/").status_code == 200
    assert NewsAsset.objects.get(pk=aid).is_displayable()
    c.patch(ADMIN + f"assets/{aid}/", {"caption": "changed"}, format="json")
    assert NewsAsset.objects.get(pk=aid).approval_state == "pending"  # any edit needs clearing again


def test_category_crud_and_audit(staff):
    from apps.audit.models import AuditLog

    c = client_for(staff)
    r = c.post(ADMIN + "categories/", {"name": "Business", "slug": "business"}, format="json")
    assert r.status_code == 201
    cid = r.json()["data"]["id"]
    assert c.patch(ADMIN + f"categories/{cid}/", {"name": "Economy"}, format="json").status_code == 200
    assert c.delete(ADMIN + f"categories/{cid}/").status_code == 204
    assert {"news.category_create", "news.category_update", "news.category_delete"} <= set(AuditLog.objects.values_list("action", flat=True))
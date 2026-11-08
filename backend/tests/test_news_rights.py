"""News Phase 2: who decides what may be republished. The rights gate, the approval workflow and the staff-only API."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.news.models import NewsRightsRecord, NewsSource
from apps.news.services import rights

from .marketplace_helpers import client_for
from .news_helpers import ADMIN, API, make_record, make_source

pytestmark = pytest.mark.django_db


# ---- the rights gate -----------------------------------------------------------------------
def test_approved_source_with_record_is_allowed():
    source = make_source()
    make_record(source)
    d = rights.evaluate(source)
    assert d.allowed and d.full_text and d.commercial and d.modification and d.attribution_required


def test_no_record_means_no_republishing():
    d = rights.evaluate(make_source())
    assert not d.allowed and "no_rights_record" in d.reasons


@pytest.mark.parametrize("state", ["pending", "suspended", "rejected"])
def test_unapproved_source_is_denied(state):
    source = make_source(approval_state=state)
    make_record(source)
    d = rights.evaluate(source)
    assert not d.allowed and "source_not_approved" in d.reasons


def test_inactive_source_is_denied():
    source = make_source(is_active=False)
    make_record(source)
    assert "source_inactive" in rights.evaluate(source).reasons


def test_draft_expired_and_future_records_do_not_count():
    source = make_source()
    make_record(source, status="draft")
    make_record(source, effective_until=timezone.now() - timedelta(hours=1))
    make_record(source, effective_from=timezone.now() + timedelta(days=3))
    assert not rights.evaluate(source).allowed


def test_record_narrows_but_never_widens_the_source():
    narrow_source = make_source(allows_full_text=False, allows_commercial_use=False)
    make_record(narrow_source, allows_full_text=True, allows_commercial_use=True)
    d = rights.evaluate(narrow_source)
    assert d.allowed and not d.full_text and not d.commercial
    wide_source = make_source("wide", allows_full_text=True, allows_commercial_use=True)
    make_record(wide_source, allows_full_text=False, allows_commercial_use=False)
    d = rights.evaluate(wide_source)
    assert d.allowed and not d.full_text and not d.commercial
    assert "record_narrows_full_text" in d.reasons


def test_metadata_only_source_never_allows_text():
    source = make_source(source_type="metadata_only")
    make_record(source)
    d = rights.evaluate(source)
    assert not d.allowed and not d.full_text


def test_a_record_of_another_source_is_refused():
    a, b = make_source("a"), make_source("b", name="B")
    record = make_record(b)
    assert "record_belongs_to_another_source" in rights.evaluate(a, record=record).reasons


def test_newest_record_in_force_wins():
    source = make_source()
    make_record(source, title="old", allows_full_text=False, effective_from=timezone.now() - timedelta(days=30))
    new = make_record(source, title="new", effective_from=timezone.now() - timedelta(days=1))
    assert rights.evaluate(source).record == new


def test_attribution_line_fills_known_tokens_only():
    source = make_source(attribution_template="By {author} for {source} ({licence}) {original_url} {unknown}")
    record = make_record(source, licence="CC BY 4.0")
    line = rights.render_attribution(source, record, author="Ada", original_url="https://example.com/a")
    assert line == "By Ada for Daily Example (CC BY 4.0) https://example.com/a {unknown}"


# ---- state changes ---------------------------------------------------------------------------
def test_record_cannot_be_approved_without_evidence(staff):
    record = make_record(make_source(), status="draft", evidence_note="", evidence_url="")
    with pytest.raises(rights.RightsError):
        rights.approve_record(record, staff)


def test_source_cannot_be_approved_without_evidence(staff):
    source = make_source(approval_state="pending", terms_url="", evidence_ref="")
    with pytest.raises(rights.RightsError):
        rights.approve_source(source, staff)


def test_revoking_the_last_record_notifies_loss_handlers(staff):
    seen = []
    handler = lambda source, reason: seen.append((source.pk, reason))  # noqa: E731
    rights.LOSS_HANDLERS.append(handler)
    try:
        source = make_source()
        record = make_record(source)
        rights.revoke_record(record, staff, "Publisher withdrew permission")
    finally:
        rights.LOSS_HANDLERS.remove(handler)
    record.refresh_from_db()
    assert record.status == "revoked" and record.revoked_reason
    assert seen == [(source.pk, "rights_revoked")]


def test_revoking_one_of_two_records_does_not_quarantine(staff):
    seen = []
    handler = lambda source, reason: seen.append(reason)  # noqa: E731
    rights.LOSS_HANDLERS.append(handler)
    try:
        source = make_source()
        make_record(source, title="a")
        second = make_record(source, title="b")
        rights.revoke_record(second, staff, "Replaced")
    finally:
        rights.LOSS_HANDLERS.remove(handler)
    assert seen == []


def test_revoke_needs_a_reason(staff):
    with pytest.raises(rights.RightsError):
        rights.revoke_record(make_record(make_source()), staff, "  ")


def test_suspending_a_source_switches_it_off_and_notifies(staff):
    seen = []
    handler = lambda source, reason: seen.append(reason)  # noqa: E731
    rights.LOSS_HANDLERS.append(handler)
    try:
        source = make_source()
        rights.suspend_source(source, staff)
    finally:
        rights.LOSS_HANDLERS.remove(handler)
    source.refresh_from_db()
    assert source.approval_state == "suspended" and not source.is_active and seen == ["source_suspended"]


def test_expire_due_records_closes_them_and_notifies():
    seen = []
    handler = lambda source, reason: seen.append(reason)  # noqa: E731
    rights.LOSS_HANDLERS.append(handler)
    try:
        source = make_source()
        record = make_record(source, effective_from=timezone.now() - timedelta(days=5), effective_until=timezone.now() - timedelta(minutes=1))
        assert rights.expire_due_records() == 1
    finally:
        rights.LOSS_HANDLERS.remove(handler)
    record.refresh_from_db()
    assert record.status == "expired" and seen == ["rights_expired"]


# ---- API -------------------------------------------------------------------------------------
def test_admin_api_is_staff_only(client, user, staff):
    assert client.get(ADMIN + "sources/").status_code in (401, 403)
    assert client_for(user).get(ADMIN + "sources/").status_code == 403
    assert client_for(staff).get(ADMIN + "sources/").status_code == 200


def test_news_can_be_switched_off(staff, settings):
    settings.NEWS_ENABLED = False
    assert client_for(staff).get(ADMIN + "sources/").status_code == 404
    assert client_for(staff).get(API + "config/").status_code == 404


def test_config_reports_flags(client, settings):
    settings.NEWS_PUBLIC_ENABLED = True
    body = client.get(API + "config/").json()["data"]
    assert body["enabled"] is True and body["public"] is True


def test_full_workflow_through_the_api(staff):
    c = client_for(staff)
    r = c.post(ADMIN + "sources/", {"name": "Example Wire", "slug": "example-wire", "source_type": "licensed", "terms_url": "https://example.com/terms",
                                    "allows_full_text": True}, format="json")
    assert r.status_code == 201, r.content
    sid = r.json()["data"]["id"]
    assert r.json()["data"]["approval_state"] == "pending"
    assert c.post(ADMIN + f"sources/{sid}/activate/").status_code == 400  # not approved yet
    assert c.post(ADMIN + f"sources/{sid}/approve/").status_code == 200
    r = c.post(ADMIN + f"sources/{sid}/rights/", {"title": "Agreement", "licence": "Syndication", "basis": "syndication_agreement",
                                                  "allows_full_text": True, "evidence_note": "Signed copy filed"}, format="json")
    assert r.status_code == 201, r.content
    rid = r.json()["data"]["id"]
    assert c.get(ADMIN + f"sources/{sid}/decision/").json()["data"]["allowed"] is False  # draft record does not count
    assert c.post(ADMIN + f"sources/{sid}/activate/").status_code == 200
    assert c.post(ADMIN + f"rights/{rid}/approve/").status_code == 200
    assert c.get(ADMIN + f"sources/{sid}/decision/").json()["data"]["allowed"] is True
    assert c.patch(ADMIN + f"rights/{rid}/", {"title": "Changed"}, format="json").status_code == 400  # approved records are not edited
    assert c.post(ADMIN + f"rights/{rid}/revoke/", {"reason": ""}, format="json").status_code == 400
    assert c.post(ADMIN + f"rights/{rid}/revoke/", {"reason": "Agreement ended"}, format="json").status_code == 200
    assert c.get(ADMIN + f"sources/{sid}/decision/").json()["data"]["allowed"] is False
    actions = set(AuditLog.objects.filter(action__startswith="news.").values_list("action", flat=True))
    assert {"news.source_create", "news.source_approve", "news.rights_create", "news.rights_approve", "news.rights_revoke"} <= actions


def test_source_validation(staff):
    c = client_for(staff)
    base = {"name": "X", "slug": "x"}
    assert c.post(ADMIN + "sources/", {**base, "adapter": "rss"}, format="json").status_code == 400  # feed address missing
    assert c.post(ADMIN + "sources/", {**base, "adapter": "rss", "feed_url": "http://example.com/feed"}, format="json").status_code == 400
    assert c.post(ADMIN + "sources/", {**base, "poll_interval_minutes": 1}, format="json").status_code == 400
    r = c.post(ADMIN + "sources/", {**base, "source_type": "metadata_only", "allows_full_text": True}, format="json")
    assert r.status_code == 201 and r.json()["data"]["allows_full_text"] is False


def test_approval_state_cannot_be_set_directly(staff):
    c = client_for(staff)
    r = c.post(ADMIN + "sources/", {"name": "Sneaky", "slug": "sneaky", "approval_state": "approved", "is_active": True}, format="json")
    assert r.status_code == 201
    assert r.json()["data"]["approval_state"] == "pending" and r.json()["data"]["is_active"] is False
    sid = r.json()["data"]["id"]
    c.patch(ADMIN + f"sources/{sid}/", {"approval_state": "approved"}, format="json")
    assert NewsSource.objects.get(pk=sid).approval_state == "pending"


def test_rights_dates_must_make_sense(staff):
    source = make_source()
    now = timezone.now()
    r = client_for(staff).post(ADMIN + f"sources/{source.pk}/rights/", {"title": "t", "licence": "l", "basis": "open_licence",
                                "effective_from": now.isoformat(), "effective_until": (now - timedelta(days=1)).isoformat()}, format="json")
    assert r.status_code == 400
    assert NewsRightsRecord.objects.count() == 0
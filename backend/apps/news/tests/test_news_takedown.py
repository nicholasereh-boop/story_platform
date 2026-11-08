"""News Phase 5: the copyright complaint form and the staff takedown workflow."""
import pytest

from apps.audit.models import AuditLog
from apps.news.models import NewsTakedown
from apps.news.services import takedown

from .marketplace_helpers import client_for
from .news_helpers import ADMIN, API, make_live_article, make_record, make_source

pytestmark = pytest.mark.django_db
FORM = {"name": "Pat", "email": "pat@example.com", "claim": "copyright", "message": "This article copies my work without permission."}


@pytest.fixture
def public(settings):
    settings.NEWS_PUBLIC_ENABLED = True


@pytest.fixture
def live(staff):
    source = make_source()
    make_record(source)
    return make_live_article(source, staff)


def test_form_records_a_complaint_and_matches_the_article_by_link_or_slug(client, public, live):
    r = client.post(API + "takedown/", {**FORM, "article": f"https://site.example/news/{live.slug}/"}, format="json")
    assert r.status_code == 201 and r.json()["data"] == {"received": True}
    client.post(API + "takedown/", {**FORM, "article": live.slug}, format="json")
    assert list(NewsTakedown.objects.values_list("article_id", flat=True)) == [live.pk, live.pk]
    assert AuditLog.objects.filter(action="news.takedown_receive").count() == 2


def test_form_answers_the_same_for_unknown_articles(client, public):
    r = client.post(API + "takedown/", {**FORM, "article": "no-such-article"}, format="json")
    assert r.status_code == 201 and r.json()["data"] == {"received": True}
    assert NewsTakedown.objects.get().article_id is None


def test_form_validates_and_is_rate_limited(client, public, settings):
    assert client.post(API + "takedown/", {**FORM, "email": "nope"}, format="json").status_code == 400
    assert client.post(API + "takedown/", {**FORM, "message": "short"}, format="json").status_code == 400
    assert client.post(API + "takedown/", {**FORM, "name": "<b>x</b>"}, format="json").status_code == 400
    codes = [client.post(API + "takedown/", FORM, format="json").status_code for _ in range(7)]
    assert 429 in codes


def test_form_is_off_until_news_is_public(client, settings):
    settings.NEWS_PUBLIC_ENABLED = False
    assert client.post(API + "takedown/", FORM, format="json").status_code == 404


def test_hold_hides_the_article_at_once_and_dismiss_restores_it_to_review(staff, live):
    t = takedown.receive(name="Pat", email="p@example.com", ref=live.slug, claim="copyright", message="x" * 20)
    takedown.hold(t, staff)
    live.refresh_from_db()
    assert live.status == "quarantined" and "complaint" in live.quarantine_reason and t.status == "on_hold"
    takedown.dismiss(t, staff, "Checked: licence covers it")
    live.refresh_from_db()
    assert live.status == "pending" and t.status == "dismissed"  # never straight back to public


def test_uphold_withdraws_the_article(staff, live):
    t = takedown.receive(name="Pat", email="p@example.com", ref=live.slug, claim="copyright", message="x" * 20)
    takedown.uphold(t, staff, "Agreement did not cover this piece")
    live.refresh_from_db()
    assert live.status == "withdrawn" and t.status == "upheld" and t.handled_by == staff


def test_notes_are_required_and_closed_complaints_stay_closed(staff, live):
    t = takedown.receive(name="Pat", email="p@example.com", ref=live.slug, claim="copyright", message="x" * 20)
    with pytest.raises(takedown.TakedownError):
        takedown.dismiss(t, staff, " ")
    takedown.dismiss(t, staff, "ok")
    with pytest.raises(takedown.TakedownError):
        takedown.uphold(t, staff, "later")


def test_unmatched_complaint_cannot_be_held(staff):
    t = takedown.receive(name="Pat", email="p@example.com", ref="nothing", claim="other", message="x" * 20)
    with pytest.raises(takedown.TakedownError):
        takedown.hold(t, staff)


def test_staff_api_workflow_and_permissions(client, user, staff, live):
    t = takedown.receive(name="Pat", email="p@example.com", ref=live.slug, claim="copyright", message="x" * 20)
    assert client.get(ADMIN + "takedowns/").status_code in (401, 403)
    assert client_for(user).get(ADMIN + "takedowns/").status_code == 403
    c = client_for(staff)
    listing = c.get(ADMIN + "takedowns/?status=open").json()["data"]
    assert listing[0]["article"]["slug"] == live.slug
    assert c.post(ADMIN + f"takedowns/{t.pk}/hold/").status_code == 200
    assert c.post(ADMIN + f"takedowns/{t.pk}/uphold/", {"note": ""}, format="json").status_code == 400
    assert c.post(ADMIN + f"takedowns/{t.pk}/uphold/", {"note": "Confirmed"}, format="json").status_code == 200
    assert c.post(ADMIN + f"takedowns/{t.pk}/dismiss/", {"note": "again"}, format="json").status_code == 400
    assert {"news.takedown_hold", "news.takedown_uphold"} <= set(AuditLog.objects.values_list("action", flat=True))


def test_config_exposes_the_copyright_contact(client, settings):
    settings.NEWS_COPYRIGHT_CONTACT = "legal@example.com"
    assert client.get(API + "config/").json()["data"]["copyright_contact"] == "legal@example.com"


def test_complaint_does_not_break_when_mail_fails(public, client, settings, monkeypatch):
    settings.NEWS_TAKEDOWN_NOTIFY_EMAIL = "editors@example.com"

    def boom(*a, **k):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("apps.news.services.takedown.send_mail", boom)
    assert client.post(API + "takedown/", FORM, format="json").status_code == 201
"""News Phase 6: reader comments, staff moderation, and how comments follow the article's rights."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.news.models import NewsComment
from apps.news.services import articles

from .marketplace_helpers import client_for
from .news_helpers import ADMIN, API, make_live_article, make_record, make_source

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def on(settings):
    settings.NEWS_PUBLIC_ENABLED = True
    settings.NEWS_COMMENTS_ENABLED = True
    settings.NEWS_COMMENT_MODERATION = False


@pytest.fixture
def live(staff):
    source = make_source()
    make_record(source)
    return make_live_article(source, staff)


def url(article):
    return API + f"articles/{article.slug}/comments/"


def test_anyone_can_read_but_only_logged_in_readers_can_write(client, user, live):
    assert client.get(url(live)).status_code == 200
    assert client.post(url(live), {"body": "Hello"}, format="json").status_code in (401, 403)
    r = client_for(user).post(url(live), {"body": "Good reporting"}, format="json")
    assert r.status_code == 201 and r.json()["data"]["status"] == "approved" and r.json()["data"]["is_mine"] is True
    listing = client.get(url(live)).json()["data"]
    assert [c["body"] for c in listing] == ["Good reporting"]
    assert "email" not in listing[0] and "user" not in listing[0]  # display name only


def test_comments_are_off_until_enabled(client, user, live, settings):
    settings.NEWS_COMMENTS_ENABLED = False
    assert client.get(url(live)).status_code == 404
    assert client_for(user).post(url(live), {"body": "Hi"}, format="json").status_code == 404


def test_comment_text_is_plain_text_and_the_spam_rules_apply(user, live):
    c = client_for(user)
    html = c.post(url(live), {"body": "<script>alert(1)</script>"}, format="json")
    assert html.status_code == 201 and NewsComment.objects.get().body == "<script>alert(1)</script>"  # stored as text; the page shows it as text
    assert c.post(url(live), {"body": "   "}, format="json").status_code == 400
    assert c.post(url(live), {"body": "x" * 2001}, format="json").status_code == 400
    assert c.post(url(live), {"body": "see https://a.example https://b.example https://c.example"}, format="json").status_code == 400
    assert c.post(url(live), {"body": "<script>alert(1)</script>"}, format="json").status_code == 400  # same text again within the hour


def test_posting_is_rate_limited(user, live):
    c = client_for(user)
    codes = [c.post(url(live), {"body": f"Comment number {i}"}, format="json").status_code for i in range(22)]
    assert codes[:20] == [201] * 20 and 429 in codes[20:]


def test_moderation_mode_holds_comments_for_staff_and_shows_them_only_to_the_author(client, user, staff, live, settings):
    settings.NEWS_COMMENT_MODERATION = True
    r = client_for(user).post(url(live), {"body": "Waiting for approval"}, format="json")
    assert r.json()["data"]["status"] == "pending"
    assert client.get(url(live)).json()["data"] == []
    assert [c["body"] for c in client_for(user).get(url(live)).json()["data"]] == ["Waiting for approval"]
    cid = r.json()["data"]["id"]
    assert client_for(user).post(ADMIN + f"comments/{cid}/approve/").status_code == 403
    assert client_for(staff).post(ADMIN + f"comments/{cid}/approve/").status_code == 200
    assert [c["body"] for c in client.get(url(live)).json()["data"]] == ["Waiting for approval"]
    assert AuditLog.objects.filter(action="news.comment_approve").count() == 1


def test_staff_can_hide_and_delete_and_list_with_filters(client, user, staff, live):
    cid = client_for(user).post(url(live), {"body": "Rude comment"}, format="json").json()["data"]["id"]
    s = client_for(staff)
    assert s.post(ADMIN + f"comments/{cid}/hide/").status_code == 200
    assert client.get(url(live)).json()["data"] == []
    rows = s.get(ADMIN + "comments/?status=hidden").json()["data"]
    assert rows[0]["email"] == user.email and rows[0]["article"]["slug"] == live.slug
    assert s.post(ADMIN + f"comments/{cid}/delete/").status_code == 200
    assert s.post(ADMIN + f"comments/{cid}/explode/").status_code == 400
    assert {"news.comment_hide", "news.comment_delete"} <= set(AuditLog.objects.values_list("action", flat=True))
    assert client.get(ADMIN + "comments/").status_code in (401, 403)


def test_a_reader_can_delete_only_their_own_comment(user, staff, live):
    cid = client_for(user).post(url(live), {"body": "Mine"}, format="json").json()["data"]["id"]
    assert client_for(staff).delete(API + f"comments/{cid}/").status_code == 404  # not the author: staff use the moderation endpoints
    assert client_for(user).delete(API + f"comments/{cid}/").status_code == 200
    assert client_for(user).delete(API + f"comments/{cid}/").status_code == 200  # harmless to repeat
    assert NewsComment.objects.get(pk=cid).status == "deleted"


def test_comments_disappear_with_the_article(client, user, staff, live):
    client_for(user).post(url(live), {"body": "Still here?"}, format="json")
    articles.withdraw(live, staff, "complaint upheld")
    assert client.get(url(live)).status_code == 404
    assert client_for(user).post(url(live), {"body": "Another"}, format="json").status_code == 404
    assert NewsComment.objects.count() == 1  # kept for the record, just not shown


def test_comments_disappear_when_the_licence_lapses(client, user, live):
    client_for(user).post(url(live), {"body": "Nice"}, format="json")
    live.rights_record.effective_until = timezone.now() - timedelta(minutes=1)
    live.rights_record.save()
    assert client.get(url(live)).status_code == 404
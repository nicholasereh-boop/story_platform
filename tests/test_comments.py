"""Reader-facing comments: posting, moderation modes, visibility, replies, edit/delete/report, spam, throttles, counts."""
import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from apps.comments import services
from apps.comments.models import Comment, CommentReport
from apps.comments.text import DELETED_PLACEHOLDER

from .engagement_helpers import (
    BASE, add_comment, client_for, comments_url, ids, list_comments, make_story, make_user, post_comment, reload_counts,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------- posting
def test_verified_user_can_comment_and_count_updates():
    story, user = make_story(), make_user()
    r = post_comment(client_for(user), story, "Lovely ending")
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["body"] == "Lovely ending" and data["status"] == "approved" and data["is_mine"] is True
    assert reload_counts(story)[1] == 1


def test_unverified_and_anonymous_cannot_comment():
    story = make_story()
    unverified = post_comment(client_for(make_user("u@example.com", verified=False)), story)
    assert unverified.status_code == 403 and "verify" in unverified.json()["message"].lower()
    anon = post_comment(client_for(), story)
    assert anon.status_code in (401, 403)
    assert Comment.objects.count() == 0


def test_cannot_comment_on_non_public_story():
    user = make_user()
    for status in ("draft", "scheduled", "archived"):
        assert post_comment(client_for(user), make_story(status=status)).status_code == 404
        assert list_comments(client_for(), make_story(f"T {status}", status=status)).status_code == 404


# ---------------------------------------------------------------- moderation modes
def test_mode_off_publishes_immediately():
    story = make_story()
    assert services.get_moderation_mode() == "off"  # the default
    assert post_comment(client_for(make_user()), story).json()["data"]["status"] == "approved"


def test_mode_approve_first_makes_everything_pending():
    story, user = make_story(), make_user()
    services.set_moderation_mode("approve_first")
    r = post_comment(client_for(user), story)
    assert r.json()["data"]["status"] == "pending"
    assert reload_counts(story)[1] == 0  # pending comments are not counted
    assert post_comment(client_for(user), story, "Second one").json()["data"]["status"] == "pending"


def test_mode_approve_first_time_only_holds_new_commenters():
    story, user = make_story(), make_user()
    services.set_moderation_mode("approve_first_time")
    first = post_comment(client_for(user), story, "First").json()["data"]
    assert first["status"] == "pending"
    still_new = post_comment(client_for(user), story, "Before approval").json()["data"]
    assert still_new["status"] == "pending"  # no approved comment yet
    services.set_status(Comment.objects.get(pk=first["id"]), "approved")
    assert post_comment(client_for(user), story, "After approval").json()["data"]["status"] == "approved"


def test_staff_comments_skip_moderation():
    services.set_moderation_mode("approve_first")
    r = post_comment(client_for(make_user("s@example.com", staff=True)), make_story())
    assert r.json()["data"]["status"] == "approved"


# ---------------------------------------------------------------- visibility matrix
def test_visibility_matrix_per_status():
    story = make_story()
    author, other, staff = make_user("a@example.com"), make_user("o@example.com"), make_user("s@example.com", staff=True)
    by_status = {s: add_comment(story, author, f"{s} body", status=s).id for s in ("pending", "approved", "hidden", "deleted")}
    viewers = {"anonymous": client_for(), "author": client_for(author), "other": client_for(other), "staff": client_for(staff)}
    expected = {
        "anonymous": {"approved"},
        "author": {"approved", "pending"},  # own pending, marked pending
        "other": {"approved"},
        "staff": {"approved"},  # staff moderate in the admin screen, the public list is the reader view
    }
    for name, client in viewers.items():
        seen = set(ids(list_comments(client, story)))
        assert seen == {by_status[s] for s in expected[name]}, name
    mine = {c["id"]: c for c in list_comments(viewers["author"], story).json()["data"]}
    assert mine[by_status["pending"]]["status"] == "pending"


def test_list_is_oldest_first_and_paginated_by_20():
    story, user = make_story(), make_user()
    made = [add_comment(story, user, f"c{i}").id for i in range(25)]
    page1 = list_comments(client_for(), story).json()
    assert [c["id"] for c in page1["data"]] == made[:20]
    assert page1["pagination"]["count"] == 25 and page1["pagination"]["has_next"] is True
    assert ids(list_comments(client_for(), story, page=2)) == made[20:]


# ---------------------------------------------------------------- replies
def test_replies_are_one_level_deep_and_nested():
    story, user = make_story(), make_user()
    client = client_for(user)
    top = post_comment(client, story, "Top").json()["data"]
    reply = post_comment(client, story, "Reply", parent=top["id"]).json()["data"]
    assert reply["parent"] == top["id"]
    nested = post_comment(client, story, "Reply to reply", parent=reply["id"]).json()["data"]
    assert nested["parent"] == top["id"]  # attached to the top-level parent, not the reply
    listing = list_comments(client_for(), story).json()["data"]
    assert len(listing) == 1 and [r["body"] for r in listing[0]["replies"]] == ["Reply", "Reply to reply"]
    assert all(r["replies"] == [] for r in listing[0]["replies"])
    assert reload_counts(story)[1] == 3


def test_reply_to_missing_other_story_or_unapproved_comment_is_rejected():
    story, other_story, user = make_story(), make_story("Other"), make_user()
    client = client_for(user)
    pending = add_comment(story, make_user("p@example.com"), status="pending")
    foreign = add_comment(other_story, user)
    for parent in (99999, pending.id, foreign.id):
        r = post_comment(client, story, "Reply", parent=parent)
        assert r.status_code == 400 and r.json()["message"]


def test_hidden_parent_hides_its_replies_and_count():
    story, user = make_story(), make_user()
    top = add_comment(story, user, "Top")
    add_comment(story, make_user("b@example.com"), "Reply", parent=top)
    assert reload_counts(story)[1] == 2
    services.set_status(top, "hidden")
    assert ids(list_comments(client_for(), story)) == []
    assert reload_counts(story)[1] == 0  # the reply is hidden with its parent
    services.set_status(top, "approved")
    assert reload_counts(story)[1] == 2
    assert reply_bodies(list_comments(client_for(), story)) == ["Reply"]


def reply_bodies(response):
    return [r["body"] for c in response.json()["data"] for r in c["replies"]]


def test_deleted_parent_with_replies_shows_placeholder():
    story, user = make_story(), make_user()
    top = add_comment(story, user, "Secret words")
    add_comment(story, make_user("b@example.com"), "Still here", parent=top)
    services.set_status(top, "deleted")
    top_json = list_comments(client_for(), story).json()["data"][0]
    assert top_json["body"] == DELETED_PLACEHOLDER and top_json["author"] is None and top_json["status"] == "deleted"
    assert "Secret words" not in json.dumps(top_json)
    assert reload_counts(story)[1] == 1  # the reply is still visible and counted


# ---------------------------------------------------------------- edit
def test_owner_can_edit_inside_window_and_edited_at_is_set():
    story, user = make_story(), make_user()
    comment = add_comment(story, user, "Typo")
    r = client_for(user).patch(f"{BASE}comments/{comment.id}/", {"body": "Fixed"}, format="json")
    assert r.status_code == 200 and r.json()["data"]["body"] == "Fixed" and r.json()["data"]["edited_at"]
    comment.refresh_from_db()
    assert comment.edited_at is not None


def test_edit_after_window_is_refused(settings):
    settings.COMMENT_EDIT_WINDOW_MINUTES = 15
    story, user = make_story(), make_user()
    comment = add_comment(story, user, "Old")
    Comment.objects.filter(pk=comment.pk).update(created_at=timezone.now() - timedelta(minutes=16))
    r = client_for(user).patch(f"{BASE}comments/{comment.id}/", {"body": "Late"}, format="json")
    assert r.status_code == 403 and "15 minutes" in r.json()["message"]
    comment.refresh_from_db()
    assert comment.body == "Old"


def test_only_the_owner_can_edit():
    story, owner, other = make_story(), make_user(), make_user("o@example.com")
    comment = add_comment(story, owner, "Mine")
    url = f"{BASE}comments/{comment.id}/"
    assert client_for(other).patch(url, {"body": "Hijack"}, format="json").status_code == 403
    staff = make_user("s@example.com", staff=True)
    assert client_for(staff).patch(url, {"body": "Staff edit"}, format="json").status_code == 403
    assert client_for().patch(url, {"body": "Anon"}, format="json").status_code in (401, 403)


def test_edit_applies_the_same_input_rules():
    story, user = make_story(), make_user()
    comment = add_comment(story, user, "Fine")
    url = f"{BASE}comments/{comment.id}/"
    assert client_for(user).patch(url, {"body": "   "}, format="json").status_code == 400
    assert client_for(user).patch(url, {"body": "x" * 2001}, format="json").status_code == 400
    assert client_for(user).patch(url, {"body": "a http://a.co b http://b.co c http://c.co"}, format="json").status_code == 400


def test_cannot_see_or_edit_someone_elses_pending_or_hidden_comment():
    story, owner, other = make_story(), make_user(), make_user("o@example.com")
    for status in ("pending", "hidden"):
        comment = add_comment(story, owner, status, status=status)
        url = f"{BASE}comments/{comment.id}/"
        assert client_for(other).patch(url, {"body": "x"}, format="json").status_code == 404
        assert client_for(other).delete(url).status_code == 404


# ---------------------------------------------------------------- delete
def test_owner_soft_delete_replaces_body_and_updates_count():
    story, user = make_story(), make_user()
    comment = add_comment(story, user, "Regret")
    assert reload_counts(story)[1] == 1
    r = client_for(user).delete(f"{BASE}comments/{comment.id}/")
    assert r.status_code == 200 and r.json()["data"]["body"] == DELETED_PLACEHOLDER
    comment.refresh_from_db()
    assert comment.status == "deleted" and comment.body == "Regret"  # soft delete: the row stays
    assert ids(list_comments(client_for(), story)) == []
    assert reload_counts(story)[1] == 0
    assert client_for(user).delete(f"{BASE}comments/{comment.id}/").status_code == 200  # idempotent
    assert reload_counts(story)[1] == 0


def test_staff_can_delete_but_other_readers_cannot():
    story, owner = make_story(), make_user()
    comment = add_comment(story, owner, "Rude")
    url = f"{BASE}comments/{comment.id}/"
    assert client_for(make_user("o@example.com")).delete(url).status_code == 403
    assert client_for().delete(url).status_code in (401, 403)
    assert client_for(make_user("s@example.com", staff=True)).delete(url).status_code == 200
    comment.refresh_from_db()
    assert comment.status == "deleted"


# ---------------------------------------------------------------- reports
def test_report_uniqueness_and_validation():
    story, author, reader = make_story(), make_user(), make_user("r@example.com")
    comment = add_comment(story, author, "Meh")
    url = f"{BASE}comments/{comment.id}/report/"
    client = client_for(reader)
    assert client.post(url, {"reason": "Spam"}, format="json").status_code == 201
    assert client.post(url, {"reason": "Spam again"}, format="json").status_code == 200  # harmless repeat
    assert CommentReport.objects.filter(comment=comment).count() == 1
    assert client_for(make_user("r2@example.com")).post(url, {}, format="json").status_code == 201  # reason optional
    assert client_for(make_user("r3@example.com")).post(url, {"reason": "x" * 301}, format="json").status_code == 400
    assert client_for().post(url, {}, format="json").status_code in (401, 403)


def test_only_visible_comments_can_be_reported():
    story, author, reader = make_story(), make_user(), make_user("r@example.com")
    for status in ("pending", "hidden", "deleted"):
        comment = add_comment(story, author, status, status=status)
        assert client_for(reader).post(f"{BASE}comments/{comment.id}/report/", {}, format="json").status_code == 404


# ---------------------------------------------------------------- input safety and spam
def test_body_is_cleaned_to_plain_text():
    story, user = make_story(), make_user()
    raw = "Hello\x00\x07 world\r\n\r\n\r\n\r\n\r\nNext   \n<b>bold</b> <script>alert(1)</script>"
    body = post_comment(client_for(user), story, raw).json()["data"]["body"]
    assert "\x00" not in body and "\x07" not in body and "\r" not in body
    assert "\n\n\n\n" not in body  # at most 2 blank lines
    assert "<script>alert(1)</script>" in body  # stored as plain text, never interpreted or stripped
    assert body == body.strip()


def test_whitespace_only_and_length_rules():
    story, user = make_story(), make_user()
    client = client_for(user)
    assert post_comment(client, story, "   \n\t  ").status_code == 400
    assert post_comment(client, story, "").status_code == 400
    assert post_comment(client, story, "x" * 2001).status_code == 400
    assert post_comment(client, story, "x" * 2000).status_code == 201


def test_spam_more_than_two_links_rejected():
    story, client = make_story(), client_for(make_user())
    assert post_comment(client, story, "see http://a.example and www.b.example").status_code == 201
    r = post_comment(client, story, "http://a.example http://b.example https://c.example")
    assert r.status_code == 400 and "link" in r.json()["message"].lower()


def test_spam_blocked_words(settings):
    settings.COMMENT_BLOCKED_WORDS = ["viagra", "free money"]
    story, client = make_story(), client_for(make_user())
    for bad in ("Buy VIAGRA now", "get free money today"):
        r = post_comment(client, story, bad)
        assert r.status_code == 400 and "not allowed" in r.json()["message"]
    assert post_comment(client, story, "Viagraland is a place").status_code == 201  # whole words only


def test_spam_duplicate_within_an_hour():
    story, user = make_story(), make_user()
    client = client_for(user)
    assert post_comment(client, story, "Same text").status_code == 201
    r = post_comment(client, story, "Same text")
    assert r.status_code == 400 and "already posted" in r.json()["message"]
    assert post_comment(client_for(make_user("o@example.com")), story, "Same text").status_code == 201  # other user
    Comment.objects.filter(user=user).update(created_at=timezone.now() - timedelta(hours=2))
    assert post_comment(client, story, "Same text").status_code == 201  # outside the window


# ---------------------------------------------------------------- throttles
def test_comment_throttle(monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "comment", "2/hour")
    story, client = make_story(), client_for(make_user())
    assert post_comment(client, story, "one").status_code == 201
    assert post_comment(client, story, "two").status_code == 201
    assert post_comment(client, story, "three").status_code == 429
    assert list_comments(client, story).status_code == 200  # reading is not throttled by the posting limit


def test_report_throttle(monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "report", "1/hour")
    story, author, reader = make_story(), make_user(), make_user("r@example.com")
    a, b = add_comment(story, author, "a"), add_comment(story, author, "b")
    client = client_for(reader)
    assert client.post(f"{BASE}comments/{a.id}/report/", {}, format="json").status_code == 201
    assert client.post(f"{BASE}comments/{b.id}/report/", {}, format="json").status_code == 429


# ---------------------------------------------------------------- comment_count through every status change
def test_comment_count_through_every_status_change():
    story, user = make_story(), make_user()
    comment = Comment.objects.create(story=story, user=user, body="x", status="pending")
    expected = [("approved", 1), ("hidden", 0), ("approved", 1), ("deleted", 0), ("approved", 1), ("pending", 0), ("approved", 1)]
    for status, count in expected:
        services.set_status(comment, status)
        assert reload_counts(story)[1] == count, status
        _assert_recount_agrees(story)


def test_comment_count_with_replies_through_parent_changes():
    story, user = make_story(), make_user()
    top = add_comment(story, user, "Top")
    add_comment(story, user, "R1", parent=top)
    add_comment(story, user, "R2", parent=top)
    add_comment(story, user, "R3 pending", parent=top, status="pending")
    assert reload_counts(story)[1] == 3
    for status, count in [("hidden", 0), ("approved", 3), ("deleted", 2), ("approved", 3)]:
        services.set_status(top, status)
        assert reload_counts(story)[1] == count, status
        _assert_recount_agrees(story)


def _assert_recount_agrees(story):
    """The live counter must equal what recount_engagement would compute."""
    before = reload_counts(story)
    call_command("recount_engagement")
    assert reload_counts(story) == before


def test_recount_command_repairs_comment_count():
    story, user = make_story(), make_user()
    add_comment(story, user, "a")
    add_comment(story, user, "b")
    type(story).objects.filter(pk=story.pk).update(comment_count=40)
    call_command("recount_engagement", "--dry-run")
    assert reload_counts(story)[1] == 40
    call_command("recount_engagement")
    assert reload_counts(story)[1] == 2


# ---------------------------------------------------------------- privacy and performance
def test_public_comment_responses_expose_no_emails_or_user_ids():
    story, user = make_story(), make_user("secret.person@example.com")
    top = add_comment(story, user, "Top")
    add_comment(story, make_user("other.person@example.com"), "Reply", parent=top)
    for client in (client_for(), client_for(user)):
        raw = json.dumps(list_comments(client, story).json())
        assert "example.com" not in raw and "secret.person" not in raw
    created = post_comment(client_for(user), story, "Brand new").json()["data"]
    assert set(created) == {
        "id", "parent", "body", "author", "status", "is_mine", "can_edit", "can_delete",
        "edit_expires_at", "created_at", "edited_at", "replies",
    }
    assert "example.com" not in json.dumps(created)


def test_comment_list_query_count_is_fixed():
    story = make_story()
    reader = make_user("reader2@example.com")
    top = add_comment(story, make_user("first@example.com"), "First")
    add_comment(story, make_user("r1@example.com"), "Reply", parent=top)

    def count(client):
        with CaptureQueriesContext(connection) as ctx:
            assert list_comments(client, story).status_code == 200
        return len(ctx)

    count(client_for()), count(client_for(reader))  # warm-up: one-off caches must not skew the comparison
    anon_before, user_before = count(client_for()), count(client_for(reader))
    for i in range(12):
        parent = add_comment(story, make_user(f"c{i}@example.com"), f"Comment {i}")
        add_comment(story, make_user(f"d{i}@example.com"), f"Reply {i}", parent=parent)
    assert count(client_for()) == anon_before
    assert count(client_for(reader)) == user_before

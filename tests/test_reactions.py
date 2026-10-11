"""Likes: idempotency, uniqueness, counters, visibility, throttle, public serializer additions."""
import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from rest_framework.throttling import ScopedRateThrottle

from apps.reactions.models import Like
from apps.reactions.services import like_story, unlike_story

from .engagement_helpers import BASE, client_for, make_story, make_user

pytestmark = pytest.mark.django_db


def like_url(story):
    return f"{BASE}stories/{story.slug}/like/"


def likes_url(story):
    return f"{BASE}stories/{story.slug}/likes/"


def fresh(story):
    story.refresh_from_db()
    return story.like_count


def test_like_is_idempotent(db):
    story, reader = make_story(), make_user("a@example.com")
    client = client_for(reader)
    first, second = client.post(like_url(story)), client.post(like_url(story))
    assert first.status_code == second.status_code == 200
    assert first.json()["data"] == second.json()["data"] == {"count": 1, "liked": True}
    assert Like.objects.filter(user=reader, story=story).count() == 1 and fresh(story) == 1


def test_unlike_is_idempotent_and_never_negative(db):
    story, reader = make_story(), make_user("a@example.com")
    client = client_for(reader)
    assert client.delete(like_url(story)).status_code == 200  # not liked yet: still 200
    client.post(like_url(story))
    first, second = client.delete(like_url(story)), client.delete(like_url(story))
    assert first.status_code == second.status_code == 200
    assert second.json()["data"] == {"count": 0, "liked": False}
    assert fresh(story) == 0


def test_database_enforces_one_like_per_user_and_story(db):
    story, reader = make_story(), make_user("a@example.com")
    Like.objects.create(user=reader, story=story)
    with pytest.raises(IntegrityError), transaction.atomic():
        Like.objects.create(user=reader, story=story)


def test_race_style_double_insert_counts_once(db):
    """Two requests pass the "not liked yet" stage together: the second insert hits the unique constraint."""
    story, reader = make_story(), make_user("a@example.com")
    assert like_story(reader, story) is True
    # Simulate the losing request of a race: its INSERT collides with the winner's row.
    assert like_story(reader, story) is False
    assert Like.objects.count() == 1 and fresh(story) == 1
    assert unlike_story(reader, story) is True and unlike_story(reader, story) is False
    assert fresh(story) == 0


def test_counts_match_rows_across_users(db):
    story = make_story()
    users = [make_user(f"u{i}@example.com") for i in range(4)]
    for u in users:
        client_for(u).post(like_url(story))
    client_for(users[0]).delete(like_url(story))
    assert Like.objects.filter(story=story).count() == fresh(story) == 3
    before = fresh(story)
    call_command("recount_engagement")
    assert fresh(story) == before  # the live counter already equals the real rows


def test_likes_endpoint_for_anonymous_and_reader(client, db):
    story, reader = make_story(), make_user("a@example.com")
    client_for(reader).post(like_url(story))
    anon = client.get(likes_url(story))
    assert anon.status_code == 200 and anon.json()["data"] == {"count": 1, "liked": False}
    mine = client_for(reader).get(likes_url(story))
    assert mine.json()["data"] == {"count": 1, "liked": True}
    assert "private" in mine["Cache-Control"] and "Cookie" in mine["Vary"]


def test_anonymous_cannot_like_or_unlike(client, db):
    story = make_story()
    for method in (client.post, client.delete):
        response = method(like_url(story))
        assert response.status_code in (401, 403)
        body = response.json()
        assert body["data"] is None and body["message"] and body["errors"]
    assert Like.objects.count() == 0


@pytest.mark.parametrize("status", ["draft", "scheduled", "archived"])
def test_only_public_stories_can_be_liked(db, client, status):
    story, reader = make_story(status=status), make_user("a@example.com")
    c = client_for(reader)
    assert c.post(like_url(story)).status_code == 404
    assert c.delete(like_url(story)).status_code == 404
    assert client.get(likes_url(story)).status_code == 404
    assert Like.objects.count() == 0


def test_like_throttle(db, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "like", "3/min")
    story, reader = make_story(), make_user("a@example.com")
    c = client_for(reader)
    codes = [c.post(like_url(story)).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_public_serializers_expose_counts_and_liked_by_me(client, db):
    story, reader = make_story(like_count=2, comment_count=5), make_user("a@example.com")
    item = client.get(f"{BASE}stories/").json()["data"][0]
    assert item["like_count"] == 2 and item["comment_count"] == 5 and "liked_by_me" not in item

    anon = client.get(f"{BASE}stories/{story.slug}/")
    assert "liked_by_me" not in anon.json()["data"] and "Cookie" in anon["Vary"]

    c = client_for(reader)
    c.post(like_url(story))
    mine = c.get(f"{BASE}stories/{story.slug}/")
    assert mine.json()["data"]["liked_by_me"] is True
    assert "private" in mine["Cache-Control"] and "Cookie" in mine["Vary"]
    c.delete(like_url(story))
    assert c.get(f"{BASE}stories/{story.slug}/").json()["data"]["liked_by_me"] is False


def test_recount_fixes_a_drifted_counter(db):
    story, reader = make_story(like_count=99, comment_count=42), make_user("a@example.com")
    Like.objects.create(user=reader, story=story)
    call_command("recount_engagement", "--dry-run")
    assert fresh(story) == 99  # dry run changes nothing
    call_command("recount_engagement")
    story.refresh_from_db()
    assert (story.like_count, story.comment_count) == (1, 0)

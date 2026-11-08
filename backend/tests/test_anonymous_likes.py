"""Anonymous likes: a visitor can like and unlike a story but still cannot comment; one like per person per story."""
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.reactions.models import Like
from apps.reactions.services import like_as_visitor, like_story, unlike_as_visitor, unlike_story
from apps.reactions.views import SESSION_KEY, TOKEN_RE, visitor_id_for

from .engagement_helpers import BASE, PASSWORD, client_for, comments_url, make_story, make_user

pytestmark = pytest.mark.django_db


def like_url(story):
    return f"{BASE}stories/{story.slug}/like/"


def likes_url(story):
    return f"{BASE}stories/{story.slug}/likes/"


def count(story):
    story.refresh_from_db()
    return story.like_count


# ------------------------------------------------------------------ a visitor likes and unlikes
def test_a_visitor_can_like_and_the_like_is_stored_against_a_browser_token_not_a_person():
    story, visitor = make_story(), APIClient()
    r = visitor.post(like_url(story))
    assert r.status_code == 200 and r.json()["data"] == {"count": 1, "liked": True}
    row = Like.objects.get()
    assert row.user is None and TOKEN_RE.match(row.visitor_id) and count(story) == 1
    assert "sessionid" in visitor.cookies  # rides on the existing session cookie: no new cookie exists


def test_liking_twice_counts_once_and_the_same_browser_is_remembered():
    story, visitor = make_story(), APIClient()
    first, second = visitor.post(like_url(story)), visitor.post(like_url(story))
    assert first.json()["data"] == second.json()["data"] == {"count": 1, "liked": True}
    assert Like.objects.count() == 1 and count(story) == 1
    assert visitor.get(likes_url(story)).json()["data"] == {"count": 1, "liked": True}


def test_a_different_browser_sees_the_count_but_not_my_like():
    story, me, someone = make_story(), APIClient(), APIClient()
    me.post(like_url(story))
    assert someone.get(likes_url(story)).json()["data"] == {"count": 1, "liked": False}


def test_two_visitors_are_two_likes():
    story = make_story()
    for _ in range(2):
        APIClient().post(like_url(story))
    assert Like.objects.filter(story=story, user=None).count() == count(story) == 2


def test_a_visitor_can_unlike_and_unliking_is_idempotent_and_never_negative():
    story, visitor = make_story(), APIClient()
    visitor.post(like_url(story))
    first, second = visitor.delete(like_url(story)), visitor.delete(like_url(story))
    assert first.json()["data"] == second.json()["data"] == {"count": 0, "liked": False}
    assert Like.objects.count() == 0 and count(story) == 0


def test_unliking_without_ever_liking_changes_nothing_and_starts_no_session():
    story, visitor = make_story(like_count=3), APIClient()
    r = visitor.delete(like_url(story))
    assert r.status_code == 200 and r.json()["data"] == {"count": 3, "liked": False}
    assert "sessionid" not in visitor.cookies and count(story) == 3


def test_a_visitor_cannot_remove_someone_elses_like():
    story, owner, other = make_story(), APIClient(), APIClient()
    owner.post(like_url(story))
    other.delete(like_url(story))
    assert count(story) == 1 and owner.get(likes_url(story)).json()["data"]["liked"] is True


@pytest.mark.parametrize("status", ["draft", "scheduled", "archived"])
def test_only_public_stories_can_be_liked_by_visitors(status):
    story, visitor = make_story(status=status), APIClient()
    assert visitor.post(like_url(story)).status_code == 404
    assert visitor.delete(like_url(story)).status_code == 404
    assert Like.objects.count() == 0 and "sessionid" not in visitor.cookies


def test_the_answer_is_never_shared_through_a_cache_once_the_browser_has_a_like():
    story, visitor = make_story(), APIClient()
    visitor.post(like_url(story))
    r = visitor.get(likes_url(story))
    assert "Cookie" in r["Vary"] and "private" in r["Cache-Control"]


# ------------------------------------------------------------------ but visitors still cannot comment
def test_a_visitor_can_read_comments_but_not_write_them():
    story = make_story()
    visitor = APIClient()
    assert visitor.get(comments_url(story)).status_code == 200
    r = visitor.post(comments_url(story), {"body": "hello"}, format="json")
    assert r.status_code in (401, 403) and r.json()["data"] is None and r.json()["message"]
    assert visitor.post(comments_url(story) + "", {"body": "x", "parent": 1}, format="json").status_code in (401, 403)
    reader = client_for(make_user("c@example.com"))
    assert reader.post(comments_url(story), {"body": "hello"}, format="json").status_code == 201  # logged in: allowed


def test_liking_as_a_visitor_does_not_let_that_browser_comment():
    story, visitor = make_story(), APIClient()
    visitor.post(like_url(story))
    assert visitor.post(comments_url(story), {"body": "hi"}, format="json").status_code in (401, 403)


# ------------------------------------------------------------------ security
def test_csrf_is_enforced_for_visitors_so_another_site_cannot_like_for_them():
    story = make_story()
    strict = APIClient(enforce_csrf_checks=True)
    assert strict.post(like_url(story)).status_code == 403 and Like.objects.count() == 0
    strict.get(BASE + "auth/csrf/")
    token = strict.cookies["csrftoken"].value
    assert strict.post(like_url(story), HTTP_X_CSRFTOKEN=token).status_code == 200
    assert strict.delete(like_url(story)).status_code == 403  # no header: refused again
    assert Like.objects.count() == 1


def test_visitors_are_rate_limited_per_ip_but_logged_in_readers_use_their_own_limit(monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "like_anonymous", "2/min")
    story = make_story()
    visitor = APIClient()
    assert [visitor.post(like_url(story)).status_code for _ in range(3)] == [200, 200, 429]
    reader = client_for(make_user("r@example.com"))
    assert [reader.post(like_url(story)).status_code for _ in range(3)] == [200, 200, 200]  # not held back by the visitor limit


def test_a_forged_or_malformed_token_is_ignored():
    for bad in ("short", "x" * 44, "../../etc/passwd" + "a" * 28, 12345, None, ["a" * 43]):
        assert visitor_id_for(SimpleNamespace(session={SESSION_KEY: bad})) is None
    good = "A" * 43
    assert visitor_id_for(SimpleNamespace(session={SESSION_KEY: good})) == good
    request = SimpleNamespace(session={SESSION_KEY: "short"})
    fresh = visitor_id_for(request, create=True)
    assert TOKEN_RE.match(fresh) and request.session[SESSION_KEY] == fresh


# ------------------------------------------------------------------ database rules
def test_the_database_allows_a_like_to_belong_to_exactly_one_kind_of_owner_once_per_story():
    story, user = make_story(), make_user("a@example.com")
    for bad in ({"user": user, "visitor_id": "v" * 43}, {}):  # both owners, or none
        with pytest.raises(IntegrityError), transaction.atomic():
            Like.objects.create(story=story, **bad)
    Like.objects.create(story=story, visitor_id="v" * 43)
    with pytest.raises(IntegrityError), transaction.atomic():
        Like.objects.create(story=story, visitor_id="v" * 43)
    Like.objects.create(story=make_story("Other"), visitor_id="v" * 43)  # the same browser may like a different story
    Like.objects.create(story=story, user=user)
    with pytest.raises(IntegrityError), transaction.atomic():
        Like.objects.create(story=story, user=user)


def test_the_service_layer_is_idempotent_for_visitors():
    story = make_story()
    assert like_as_visitor("v" * 43, story) is True and like_as_visitor("v" * 43, story) is False
    assert count(story) == 1
    assert unlike_as_visitor("v" * 43, story) is True and unlike_as_visitor("v" * 43, story) is False
    assert count(story) == 0


def test_the_recount_command_counts_visitor_likes_too():
    story = make_story(like_count=99)
    like_as_visitor("a" * 43, story)
    like_as_visitor("b" * 43, story)
    Like.objects.create(story=story, user=make_user("a@example.com"))
    call_command("recount_engagement")
    assert count(story) == 3


# ------------------------------------------------------------------ one person, one like, even across logging in
def test_a_browser_that_liked_as_a_visitor_keeps_its_like_when_it_logs_in_and_does_not_count_twice():
    story, user = make_story(), make_user("a@example.com")
    browser = APIClient()
    browser.post(like_url(story))
    assert browser.login(email=user.email, password=PASSWORD)  # the session key changes; its data stays
    assert browser.get(likes_url(story)).json()["data"] == {"count": 1, "liked": True}  # still recognised
    r = browser.post(like_url(story))  # liking again as the account hands the visitor's like over
    assert r.json()["data"] == {"count": 1, "liked": True}
    row = Like.objects.get()
    assert row.user_id == user.pk and row.visitor_id is None and count(story) == 1


def test_unliking_after_logging_in_removes_the_like_the_browser_made_as_a_visitor():
    story, user = make_story(), make_user("a@example.com")
    browser = APIClient()
    browser.post(like_url(story))
    browser.login(email=user.email, password=PASSWORD)
    assert browser.delete(like_url(story)).json()["data"] == {"count": 0, "liked": False}
    assert Like.objects.count() == 0


def test_if_the_account_and_the_browser_both_liked_it_is_one_person_so_one_like():
    story, user = make_story(), make_user("a@example.com")
    like_as_visitor("v" * 43, story)
    Like.objects.create(story=story, user=user)  # e.g. liked on another device
    from apps.core.counters import adjust_story_counter
    adjust_story_counter(story.pk, "like_count", +1)
    assert count(story) == 2
    assert like_story(user, story, visitor_id="v" * 43) is False
    assert count(story) == 1 and Like.objects.get().user_id == user.pk


def test_other_accounts_on_the_same_browser_cannot_take_over_a_like_that_already_belongs_to_someone():
    story, first, second = make_story(), make_user("a@example.com"), make_user("b@example.com")
    like_as_visitor("v" * 43, story)
    like_story(first, story, visitor_id="v" * 43)  # claimed by the first account
    assert like_story(second, story, visitor_id="v" * 43) is True  # the second gets their own like
    assert Like.objects.filter(story=story).count() == count(story) == 2
    assert unlike_story(first, story) is True and count(story) == 1


def test_logged_in_users_without_a_browser_token_behave_exactly_as_before():
    story, user = make_story(), make_user("a@example.com")
    client = client_for(user)
    assert client.post(like_url(story)).json()["data"] == {"count": 1, "liked": True}
    assert client.post(like_url(story)).json()["data"] == {"count": 1, "liked": True}
    assert client.delete(like_url(story)).json()["data"] == {"count": 0, "liked": False}

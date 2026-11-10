"""Phase 3: the free learning journey: catalog, outline, lessons, saved progress, lesson comments, and the unlock rules."""
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academy.models import Enrollment, LessonCommentGate, LessonProgress
from apps.academy.services import progress as progress_service

from .academy_helpers import API, free_course_with_lessons, learner, learner2, make_course, make_lesson  # noqa: F401
from .marketplace_helpers import client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def course3():
    """A free course: an intro and three 20-second lessons (short, so one progress report can complete one)."""
    course = make_course("html-basics")
    lessons = [make_lesson(course, 0, title="Welcome", is_intro=True, requires_comment_to_unlock_next=False, duration_seconds=20)]
    lessons += [make_lesson(course, n, duration_seconds=20) for n in (1, 2, 3)]
    return course, lessons


def get_lesson(client, lesson):
    return client.get(API + f"lessons/{lesson.pk}/").json()["data"]


def watch(client, lesson, seconds=20, duration=20):
    r = client.post(API + f"lessons/{lesson.pk}/progress/", {"position_seconds": seconds, "watched_seconds": seconds, "duration_seconds": duration}, format="json")
    assert r.status_code == 200, r.content
    return r.json()["data"]


def comment(client, lesson, body="I learned how tags work."):
    return client.post(API + f"lessons/{lesson.pk}/comments/", {"body": body}, format="json")


# ---- catalog and outline
def test_the_catalog_lists_only_published_courses_with_counts_and_filters(course3):
    make_course("draft-one", status="draft", title="Hidden")
    make_course("paid-one", title="Pro", access_type="paid", price=30)
    data = APIClient().get(API + "courses/").json()["data"]
    assert sorted(c["slug"] for c in data) == ["html-basics", "paid-one"]
    free = next(c for c in data if c["slug"] == "html-basics")
    assert free["lesson_count"] == 4 and free["duration_seconds"] == 80
    assert [c["slug"] for c in APIClient().get(API + "courses/?access=paid").json()["data"]] == ["paid-one"]
    assert [c["slug"] for c in APIClient().get(API + "courses/?q=html").json()["data"]] == ["html-basics"]


def test_a_draft_course_is_a_404_for_learners_but_staff_can_review_it(learner, staff_client):
    make_course("draft-one", status="draft")
    assert APIClient().get(API + "courses/draft-one/").status_code == 404
    assert client_for(learner).get(API + "courses/draft-one/").status_code == 404
    assert staff_client.get(API + "courses/draft-one/").status_code == 200


def test_the_outline_only_shows_covers_for_lessons_the_learner_may_watch(course3, learner):
    r = client_for(learner).get(API + "courses/html-basics/")
    lessons = course3[1]
    body = r.content.decode()
    data = r.json()["data"]
    assert [l["cover"] for l in data["lessons"][:2]] == [f"https://i.ytimg.com/vi/{x.youtube_id}/hqdefault.jpg" for x in lessons[:2]]
    assert all(l["cover"] is None for l in data["lessons"][2:])
    assert all(x.youtube_id not in body for x in lessons[2:])  # a locked lesson's video id never leaves the server
    assert "youtube_id" not in body
    assert [(l["title"], l["state"], l["can_view"]) for l in data["lessons"]] == [
        ("Welcome", "available", True), ("Lesson 1", "available", True), ("Lesson 2", "locked", False), ("Lesson 3", "locked", False)]
    assert data["lessons"][2]["reason"] == "locked_previous"


def test_a_visitor_sees_the_intro_but_real_lessons_ask_for_a_login(course3):
    lessons = APIClient().get(API + "courses/html-basics/").json()["data"]["lessons"]
    assert [(l["can_view"], l["reason"]) for l in lessons] == [(True, None), (False, "login_required"), (False, "login_required"), (False, "login_required")]


def test_a_visitor_gets_the_intro_cover_and_nothing_else(course3):
    course, (intro, *others) = course3
    r = APIClient().get(API + "courses/html-basics/")
    covers = [l["cover"] for l in r.json()["data"]["lessons"]]
    assert covers == [f"https://i.ytimg.com/vi/{intro.youtube_id}/hqdefault.jpg", None, None, None]
    assert all(x.youtube_id not in r.content.decode() for x in others)


def test_a_paid_course_outline_shows_covers_only_for_previews(learner):
    course = make_course("paid-one", access_type="paid", price=30)
    preview = make_lesson(course, 1, is_preview=True)
    secret = make_lesson(course, 2)
    r = client_for(learner).get(API + "courses/paid-one/")
    covers = {l["id"]: l["cover"] for l in r.json()["data"]["lessons"]}
    assert covers[preview.pk] == f"https://i.ytimg.com/vi/{preview.youtube_id}/hqdefault.jpg"
    assert covers[secret.pk] is None and secret.youtube_id not in r.content.decode()


# ---- opening lessons
def test_the_intro_plays_for_anyone_and_real_lessons_withhold_the_video_id_until_allowed(course3, learner):
    course, (intro, l1, l2, l3) = course3
    anon = APIClient()
    assert get_lesson(anon, intro)["lesson"]["youtube_id"] == intro.youtube_id
    assert get_lesson(anon, l1)["lesson"]["youtube_id"] is None and get_lesson(anon, l1)["access"]["reason"] == "login_required"
    me = client_for(learner)
    assert get_lesson(me, l1)["lesson"]["youtube_id"] == l1.youtube_id
    locked = get_lesson(me, l2)
    assert locked["lesson"]["youtube_id"] is None and locked["access"]["reason"] == "locked_previous"
    assert l2.youtube_id not in str(locked)


def test_the_introduction_never_gates_the_first_lesson(course3, learner):
    course, (intro, l1, *_rest) = course3
    me = client_for(learner)
    assert get_lesson(me, l1)["access"]["can_view"] is True  # without watching or commenting on the intro


def test_draft_lessons_do_not_exist_for_learners(course3, learner):
    course, lessons = course3
    draft = make_lesson(course, 9, is_published=False)
    assert client_for(learner).get(API + f"lessons/{draft.pk}/").status_code == 404
    assert len(APIClient().get(API + "courses/html-basics/").json()["data"]["lessons"]) == 4


# ---- watch, comment, unlock
def test_watching_a_lesson_is_not_enough_a_comment_unlocks_the_next_one(course3, learner):
    course, (intro, l1, l2, l3) = course3
    me = client_for(learner)
    done = watch(me, l1)
    assert done["progress"]["completed"] is True
    assert done["access"]["state"] == "awaiting_comment" and done["access"]["next_unlocked"] is False
    assert get_lesson(me, l2)["access"]["can_view"] is False
    r = comment(me, l1)
    assert r.status_code == 201 and r.json()["data"]["access"]["next_unlocked"] is True
    assert get_lesson(me, l2)["lesson"]["youtube_id"] == l2.youtube_id
    assert LessonCommentGate.objects.filter(learner=learner, lesson=l1).count() == 1


def test_a_comment_before_the_lesson_is_watched_is_refused_and_opens_nothing(course3, learner):
    course, (intro, l1, l2, l3) = course3
    me = client_for(learner)
    assert comment(me, l1).status_code == 409
    assert not LessonCommentGate.objects.exists()
    assert get_lesson(me, l2)["access"]["can_view"] is False


def test_a_lesson_that_does_not_ask_for_a_comment_unlocks_after_watching(course3, learner):
    course, (intro, l1, l2, l3) = course3
    l1.requires_comment_to_unlock_next = False
    l1.save()
    me = client_for(learner)
    watch(me, l1)
    assert get_lesson(me, l2)["access"]["can_view"] is True


def test_the_chain_must_be_followed_in_order(course3, learner):
    course, (intro, l1, l2, l3) = course3
    me = client_for(learner)
    watch(me, l1); comment(me, l1)
    assert get_lesson(me, l3)["access"]["can_view"] is False  # lesson 2 is open, lesson 3 still waits for it
    watch(me, l2); comment(me, l2)
    assert get_lesson(me, l3)["access"]["can_view"] is True


def test_a_comment_waiting_for_staff_approval_still_counts(course3, learner, settings):
    settings.ACADEMY_COMMENT_MODERATION = True
    course, (intro, l1, l2, l3) = course3
    me = client_for(learner)
    watch(me, l1)
    r = comment(me, l1)
    assert r.json()["data"]["comment"]["status"] == "pending"
    assert get_lesson(me, l2)["access"]["can_view"] is True


def test_a_hidden_or_deleted_comment_closes_the_next_lesson_until_the_learner_comments_again(course3, learner):
    course, (intro, l1, l2, l3) = course3
    me = client_for(learner)
    watch(me, l1)
    first = comment(me, l1).json()["data"]["comment"]
    assert get_lesson(me, l2)["access"]["can_view"] is True
    assert me.delete(API + f"comments/{first['id']}/").status_code == 204
    assert get_lesson(me, l2)["access"]["can_view"] is False
    assert comment(me, l1, "A different comment after deleting.").status_code == 201
    assert get_lesson(me, l2)["access"]["can_view"] is True  # the new comment replaced the removed one


def test_staff_hiding_a_comment_also_closes_the_gate(course3, learner):
    from apps.academy.models import LessonComment

    course, (intro, l1, l2, l3) = course3
    me = client_for(learner)
    watch(me, l1); comment(me, l1)
    LessonComment.objects.filter(lesson=l1).update(status="hidden")
    assert get_lesson(me, l2)["access"]["can_view"] is False


def test_staff_can_open_every_published_lesson(course3, staff_client):
    course, (intro, l1, l2, l3) = course3
    assert get_lesson(staff_client, l3)["access"]["can_view"] is True


# ---- saved progress
def test_progress_is_saved_per_learner_and_resumes(course3, learner, learner2):
    course, (intro, l1, *_rest) = course3
    watch(client_for(learner), l1, seconds=10)
    again = get_lesson(client_for(learner), l1)["progress"]
    assert again["position_seconds"] == 10 and again["percent"] == 50
    assert get_lesson(client_for(learner2), l1)["progress"]["percent"] == 0  # nobody else's progress leaks


def test_progress_requires_login_and_an_open_lesson(course3, learner):
    course, (intro, l1, l2, l3) = course3
    body = {"position_seconds": 5, "watched_seconds": 5, "duration_seconds": 20}
    assert APIClient().post(API + f"lessons/{l1.pk}/progress/", body, format="json").status_code in (401, 403)
    assert client_for(learner).post(API + f"lessons/{l2.pk}/progress/", body, format="json").status_code == 409  # still locked
    assert not LessonProgress.objects.filter(lesson=l2).exists()


@pytest.mark.parametrize("bad", [-1, "abc", None, True, [1], "NaN"])
def test_nonsense_progress_numbers_are_rejected(course3, learner, bad):
    course, (intro, l1, *_rest) = course3
    r = client_for(learner).post(API + f"lessons/{l1.pk}/progress/", {"position_seconds": 1, "watched_seconds": bad, "duration_seconds": 20}, format="json")
    assert r.status_code == 400


def test_forged_progress_cannot_finish_a_long_lesson_in_one_request(learner):
    course = make_course("long")
    lesson = make_lesson(course, 1, duration_seconds=600)
    done = watch(client_for(learner), lesson, seconds=600, duration=600)  # claims the whole video at once
    assert done["progress"]["completed"] is False and done["progress"]["percent"] < 10


def test_watch_time_grows_only_as_fast_as_the_clock_and_never_goes_down(learner, monkeypatch):
    course = make_course("long")
    lesson = make_lesson(course, 1, duration_seconds=600)
    now = timezone.now()
    clock = SimpleNamespace(t=now)
    monkeypatch.setattr(progress_service, "timezone", SimpleNamespace(now=lambda: clock.t))
    me = client_for(learner)
    first = watch(me, lesson, seconds=40, duration=600)["progress"]["watched_seconds"]
    assert first == 40
    clock.t = now + timezone.timedelta(seconds=10)
    second = watch(me, lesson, seconds=400, duration=600)["progress"]["watched_seconds"]  # 10 s later it cannot be 400
    assert 40 < second <= 40 + 10 * 1.5 + 15
    clock.t = now + timezone.timedelta(seconds=20)
    assert watch(me, lesson, seconds=5, duration=600)["progress"]["watched_seconds"] == second  # a lower report never lowers it
    clock.t = now + timezone.timedelta(seconds=800)
    assert watch(me, lesson, seconds=600, duration=600)["progress"]["completed"] is True  # real time passed: it can finish


def test_the_lessons_own_threshold_decides_completion(learner):
    course = make_course("thr")
    lesson = make_lesson(course, 1, duration_seconds=20, completion_threshold=50)
    assert watch(client_for(learner), lesson, seconds=9)["progress"]["completed"] is False
    assert watch(client_for(learner), lesson, seconds=10)["progress"]["completed"] is True


def test_taking_part_enrolls_the_learner(course3, learner):
    course, (intro, l1, *_rest) = course3
    assert not Enrollment.objects.exists()
    watch(client_for(learner), l1, seconds=5)
    assert Enrollment.objects.filter(learner=learner, course=course, source="free").exists()


# ---- enrolling and My learning
def test_starting_a_free_course_is_idempotent_and_paid_courses_cannot_be_joined(course3, learner):
    make_course("paid-one", access_type="paid", price=20)
    me = client_for(learner)
    assert me.post(API + "courses/html-basics/enroll/").status_code == 201
    assert me.post(API + "courses/html-basics/enroll/").status_code == 200
    assert Enrollment.objects.filter(learner=learner).count() == 1
    assert me.post(API + "courses/paid-one/enroll/").status_code == 409
    assert APIClient().post(API + "courses/html-basics/enroll/").status_code in (401, 403)


def test_my_learning_shows_progress_and_the_lesson_to_continue_with(course3, learner):
    course, (intro, l1, l2, l3) = course3
    me = client_for(learner)
    watch(me, intro); watch(me, l1); comment(me, l1)
    item = me.get(API + "my-learning/").json()["data"]["items"][0]
    assert item["slug"] == "html-basics" and item["completed"] == 2 and item["total"] == 4 and item["percent"] == 50
    assert item["next_lesson_id"] == l2.pk


# ---- comments
def test_comments_list_shows_approved_ones_and_your_own_pending_ones_only(course3, learner, learner2, settings):
    from apps.academy.models import LessonComment

    course, (intro, l1, *_rest) = course3
    LessonComment.objects.create(lesson=intro, user=learner2, body="Approved one", status="approved")
    LessonComment.objects.create(lesson=intro, user=learner2, body="Hidden one", status="hidden")
    LessonComment.objects.create(lesson=intro, user=learner2, body="Pending of other", status="pending")
    LessonComment.objects.create(lesson=intro, user=learner, body="My pending", status="pending")
    bodies = lambda c: [x["body"] for x in c.get(API + f"lessons/{intro.pk}/comments/").json()["data"]]
    assert bodies(client_for(learner)) == ["Approved one", "My pending"]
    assert bodies(APIClient()) == ["Approved one"]


def test_comments_on_a_locked_lesson_are_not_available(course3, learner):
    course, (intro, l1, l2, l3) = course3
    me = client_for(learner)
    assert me.get(API + f"lessons/{l2.pk}/comments/").json()["data"]["items"] == []
    assert comment(me, l2).status_code == 409


@pytest.mark.parametrize("body,field", [("", "body"), ("   \n ", "body"), ("x" * 6000, "body"), ("see http://a.com http://b.com http://c.com", "body")])
def test_bad_comments_are_rejected_with_a_clear_message(course3, learner, body, field):
    course, (intro, *_rest) = course3
    r = comment(client_for(learner), intro, body)
    assert r.status_code == 400 and field in r.json()["errors"]


def test_a_repeated_comment_is_refused_and_markup_is_kept_as_text(course3, learner):
    course, (intro, *_rest) = course3
    me = client_for(learner)
    assert comment(me, intro, "Use <b>bold</b> here").json()["data"]["comment"]["body"] == "Use <b>bold</b> here"
    assert comment(me, intro, "Use <b>bold</b> here").status_code == 400


def test_a_comment_needs_a_login(course3):
    course, (intro, *_rest) = course3
    assert comment(APIClient(), intro).status_code in (401, 403)


# ---- previews, paid courses and the master switch
def test_a_preview_lesson_opens_for_everyone_even_in_a_paid_course(learner):
    course = make_course("paid-one", access_type="paid", price=30)
    preview = make_lesson(course, 1, is_preview=True)
    secret = make_lesson(course, 2)
    assert get_lesson(APIClient(), preview)["lesson"]["youtube_id"] == preview.youtube_id
    locked = get_lesson(client_for(learner), secret)
    assert locked["lesson"]["youtube_id"] is None and locked["access"]["reason"] == "purchase_required"
    assert get_lesson(APIClient(), secret)["access"]["reason"] == "login_required"


def test_switching_the_academy_off_closes_the_learner_endpoints(course3, settings):
    settings.ACADEMY_ENABLED = False
    assert APIClient().get(API + "courses/").status_code == 404
    assert APIClient().get(API + "courses/html-basics/").status_code == 404
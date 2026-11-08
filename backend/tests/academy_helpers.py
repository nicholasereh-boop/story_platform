"""Helpers for the Academy tests: ready-made users, courses and lessons."""
import pytest
from django.utils import timezone

from apps.academy.models import Course, Lesson

API = "/api/v1/academy/"
VIDEO_IDS = ["dQw4w9WgXcQ", "9bZkp7q19f0", "kJQP7kiw5Fk", "3JZ_D3ELwOQ", "L_jWHffIx5E", "fJ9rUzIMcZQ"]


def make_course(slug="html-basics", **overrides):
    values = {"title": "HTML Basics", "summary": "Start here", "description": "Learn HTML from scratch.", "status": "published", "published_at": timezone.now()}
    values.update(overrides)
    if values.get("access_type") == "paid" and not values.get("price"):
        values["price"] = 49
    return Course.objects.create(slug=slug, **values)


def make_lesson(course, position, **overrides):
    values = {"title": f"Lesson {position}", "youtube_id": VIDEO_IDS[position % len(VIDEO_IDS)], "duration_seconds": 600, "is_published": True}
    values.update(overrides)
    return Lesson.objects.create(course=course, position=position, **values)


def free_course_with_lessons(slug="html-basics", intro=True, count=3, **course_overrides):
    """A free course: an optional intro (position 0) and `count` real lessons (positions 1..count), all published."""
    course = make_course(slug, **course_overrides)
    lessons = []
    if intro:
        lessons.append(make_lesson(course, 0, title="Welcome", is_intro=True, requires_comment_to_unlock_next=False))
    for n in range(1, count + 1):
        lessons.append(make_lesson(course, n))
    return course, lessons


@pytest.fixture
def learner(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(email="learner@example.com", password="Correct-horse-battery-9")


@pytest.fixture
def learner2(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(email="learner2@example.com", password="Correct-horse-battery-9")
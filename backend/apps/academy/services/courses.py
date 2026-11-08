"""Small helpers for authoring courses and lessons (staff side)."""
import re

from django.db import transaction
from django.db.models import Max

from apps.core.utils import unique_slug

from ..models import Course, CourseEntitlement, CourseOrder, Enrollment, Lesson, LessonProgress

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def make_slug(title, instance=None):
    """A unique slug that always contains a letter, so it can never be mistaken for a numeric id in a URL."""
    slug = unique_slug(Course, title, instance=instance, fallback="course")
    if slug.isdigit():
        slug = unique_slug(Course, f"course-{slug}", instance=instance, fallback="course")
    return slug


def valid_custom_slug(value):
    return bool(SLUG_RE.match(value)) and len(value) <= 90 and not value.isdigit()


def has_learner_activity(course):
    """True once anyone has enrolled, bought, been granted access or made progress: then the course may be archived, not deleted,
    and its free/paid type may no longer change."""
    return (
        Enrollment.objects.filter(course=course).exists()
        or CourseOrder.objects.filter(course=course).exists()
        or CourseEntitlement.objects.filter(course=course).exists()
        or LessonProgress.objects.filter(lesson__course=course).exists()
    )


def next_position(course):
    last = Lesson.objects.filter(course=course).aggregate(m=Max("position"))["m"]
    return 0 if last is None else last + 1


def publish_problems(course):
    """What still stops this course from being published (an empty list means it is ready)."""
    problems = []
    lessons = list(course.lessons.filter(is_published=True))
    real = [lesson for lesson in lessons if not lesson.is_intro and lesson.youtube_id]
    if not real:
        problems.append("Publish at least one lesson (not just the introduction) that has a YouTube video.")
    if any(not lesson.youtube_id for lesson in lessons):
        problems.append("Every published lesson needs a YouTube video.")
    if not course.video_rights_confirmed_at:
        problems.append("Confirm that you have the right to use the videos in this course.")
    if course.is_paid and course.price <= 0:
        problems.append("A paid course needs a price above 0.")
    return problems


@transaction.atomic
def reorder_lessons(course, ids):
    """Rewrite the positions 0..n-1 in the given order. `ids` must be exactly this course's lesson ids."""
    current = {lesson.pk: lesson for lesson in Lesson.objects.select_for_update().filter(course=course)}
    if sorted(ids) != sorted(current) or len(set(ids)) != len(ids):
        return False
    for position, pk in enumerate(ids):
        lesson = current[pk]
        if lesson.position != position:
            lesson.position = position
            lesson.save(update_fields=["position", "updated_at"])
    return True
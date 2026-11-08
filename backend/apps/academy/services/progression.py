"""The Academy's access and progression rules (docs/ARCHITECTURE.md). Every "may this learner open this lesson?" question is
answered here, on the server, from stored facts: the browser never decides. Free courses are a chain: finish a lesson (watch
it, then comment if the lesson asks for it) to open the next. Paid courses open entirely with an entitlement.

Policies written down on purpose (docs/IMPORTANT_DECISIONS.md #3, #6):
* the course introduction (is_intro) is always open and never asks for a comment;
* free previews (is_preview) can be opened by anyone;
* a comment waiting for staff approval (pending) counts toward the gate; a hidden or deleted one does NOT, so a learner whose
  comment was removed must comment again before the lessons after it open;
* staff can open every published lesson (to review the course).
"""
from ..models import LessonComment, LessonCommentGate, LessonProgress
from . import entitlements

ACTIVE_COMMENT_STATUSES = (LessonComment.Status.PENDING, LessonComment.Status.APPROVED)


def is_signed_in(user):
    return bool(user and user.is_authenticated and user.is_active)


def is_gated(course, lesson):
    """Does finishing this lesson need a comment before the next one opens? (free courses only; never the introduction)"""
    return (not course.is_paid) and lesson.requires_comment_to_unlock_next and not lesson.is_intro


def published_lessons(course):
    return list(course.lessons.filter(is_published=True))


def compute_states(user, course, lessons=None):
    """{lesson_id: state dict} for every published lesson of `course`, plus the ordered lesson list: (states, lessons).

    state: can_view, reason (login_required | locked_previous | purchase_required | None), state (locked | available | in_progress |
    awaiting_comment | completed), watch_met, comment_met, requirement_met, percent, position_seconds, watched_seconds.
    """
    lessons = published_lessons(course) if lessons is None else lessons
    signed_in = is_signed_in(user)
    staff = signed_in and user.is_staff
    progress, gates = {}, {}
    if signed_in:
        progress = {p.lesson_id: p for p in LessonProgress.objects.filter(learner=user, lesson__course=course)}
        gates = {g.lesson_id: g for g in LessonCommentGate.objects.filter(learner=user, lesson__course=course).select_related("comment")}
    entitled = bool(course.is_paid and signed_in and (staff or entitlements.has_access(user, course)))

    states = {}
    chain_open = True  # free courses: every required lesson before this one has been completed
    for lesson in lessons:
        p = progress.get(lesson.pk)
        gate = gates.get(lesson.pk)
        gated = is_gated(course, lesson)
        watch_met = bool(p and p.completed_at)
        comment_met = bool(gate and gate.comment_id and gate.comment.status in ACTIVE_COMMENT_STATUSES)
        requirement_met = watch_met and (comment_met or not gated)

        if course.is_paid:
            can_view = lesson.is_preview or entitled
            reason = None if can_view else ("purchase_required" if signed_in else "login_required")
        elif lesson.is_intro or lesson.is_preview or staff:
            can_view, reason = True, None
        elif not signed_in:
            can_view, reason = False, "login_required"
        elif chain_open:
            can_view, reason = True, None
        else:
            can_view, reason = False, "locked_previous"
        if not lesson.is_intro:
            chain_open = chain_open and requirement_met

        if not can_view:
            label = "locked"
        elif requirement_met:
            label = "completed"
        elif watch_met and gated:
            label = "awaiting_comment"
        elif p and (p.watched_seconds > 0 or p.position_seconds > 0):
            label = "in_progress"
        else:
            label = "available"
        states[lesson.pk] = {
            "can_view": can_view, "reason": reason, "state": label, "watch_met": watch_met, "comment_met": comment_met,
            "requirement_met": requirement_met, "requires_comment": gated,
            "percent": p.completion_percent if p else 0, "position_seconds": p.position_seconds if p else 0,
            "watched_seconds": p.watched_seconds if p else 0,
        }
    return states, lessons


def course_summary(states, lessons):
    """Counts for the course page and My learning, and the lesson to continue with."""
    completed = sum(1 for lesson in lessons if states[lesson.pk]["state"] == "completed")
    total = len(lessons)
    nxt = next((lesson for lesson in lessons if states[lesson.pk]["can_view"] and states[lesson.pk]["state"] != "completed"), None)
    return {"completed": completed, "total": total, "percent": int(100 * completed / total) if total else 0, "next_lesson_id": nxt.pk if nxt else None}


def neighbours(lessons, lesson):
    """(previous lesson, next lesson) in the course order."""
    ids = [lesson_.pk for lesson_ in lessons]
    i = ids.index(lesson.pk)
    return (lessons[i - 1] if i > 0 else None), (lessons[i + 1] if i + 1 < len(lessons) else None)
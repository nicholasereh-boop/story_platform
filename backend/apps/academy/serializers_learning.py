"""What learners (and visitors) see. A YouTube video id appears ONLY in the lesson payload, and only when the server has just
decided this learner may watch that lesson."""
from .serializers_authoring import thumbnail_data


def course_card_data(course):
    lesson_total = getattr(course, "lesson_total", None)
    duration = getattr(course, "duration_total", None)
    if lesson_total is None:
        published = course.lessons.filter(is_published=True)
        lesson_total, duration = published.count(), sum(lesson.duration_seconds for lesson in published)
    return {
        "id": course.pk, "slug": course.slug, "title": course.title, "summary": course.summary, "level": course.level, "category": course.category,
        "thumbnail": thumbnail_data(course.thumbnail), "access_type": course.access_type, "price": f"{course.price:.2f}", "currency": course.currency,
        "lesson_count": lesson_total, "duration_seconds": duration or 0, "published_at": course.published_at,
    }

def cover_url(lesson, state):
    """YouTube's own cover picture, for a lesson this learner may already watch. Never for a locked lesson (the address holds the id)."""
    if state["can_view"] and lesson.youtube_id:
        return f"https://i.ytimg.com/vi/{lesson.youtube_id}/hqdefault.jpg"
    return None


def curriculum_item(lesson, state):
    """One line of the course outline: no description, and a cover picture only where the learner may watch."""
    return {
        "id": lesson.pk, "title": lesson.title, "position": lesson.position, "duration_seconds": lesson.duration_seconds,
        "is_intro": lesson.is_intro, "is_preview": lesson.is_preview, "state": state["state"], "can_view": state["can_view"], "reason": state["reason"],
        "requires_comment": state["requires_comment"], "cover": cover_url(lesson, state),
    }
def access_data(state, next_state=None, next_id=None):
    return {
        "can_view": state["can_view"], "reason": state["reason"], "state": state["state"], "watch_met": state["watch_met"],
        "comment_met": state["comment_met"], "requires_comment": state["requires_comment"], "requirement_met": state["requirement_met"],
        "next_lesson_id": next_id, "next_unlocked": bool(next_state and next_state["can_view"]),
    }


def lesson_data(lesson, state):
    """The lesson page payload. `youtube_id` is withheld unless the learner may watch."""
    return {
        "id": lesson.pk, "title": lesson.title, "description": lesson.description, "position": lesson.position,
        "duration_seconds": lesson.duration_seconds, "is_intro": lesson.is_intro, "is_preview": lesson.is_preview,
        "completion_threshold": lesson.completion_threshold, "requires_comment": state["requires_comment"],
        "youtube_id": lesson.youtube_id if state["can_view"] else None,
    }
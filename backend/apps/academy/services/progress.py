"""Saving what a learner has watched. The browser reports it, so it is a SIGNAL, not proof (docs/IMPORTANT_DECISIONS.md #4):
the server only accepts watch time that real elapsed time can explain, never lets it go down, and decides completion itself
from the lesson's own completion threshold."""
from django.conf import settings
from django.utils import timezone

from ..models import Enrollment, LessonProgress

MAX_VIDEO_SECONDS = 8 * 3600  # a reported video length above this is not believed
SLACK = 1.5  # accepted watch time per real second (a little more than 1x to allow for network and timer jitter)


def _clamp(value, low, high):
    return max(low, min(high, value))


def record_progress(user, lesson, position_seconds, watched_seconds, duration_seconds, now=None):
    """Update (or create) the learner's progress for a lesson and return it. Numbers are whole seconds, already validated."""
    now = now or timezone.now()
    interval = max(5, settings.ACADEMY_PROGRESS_UPDATE_INTERVAL_SECONDS)
    progress, _ = LessonProgress.objects.select_for_update().get_or_create(learner=user, lesson=lesson)

    # The video length: the lesson's own value wins; otherwise the player's report (within reason).
    duration = lesson.duration_seconds or progress.duration_seconds or _clamp(duration_seconds, 0, MAX_VIDEO_SECONDS)
    if lesson.duration_seconds == 0 and duration_seconds:
        duration = _clamp(duration_seconds, 0, MAX_VIDEO_SECONDS)

    # Watch time can only grow as fast as the clock allows since the last report (the first report gets a small allowance).
    if progress.last_reported_at is None:
        allowance = interval * 3
    else:
        allowance = (now - progress.last_reported_at).total_seconds() * SLACK + interval
    accepted = min(watched_seconds, progress.watched_seconds + int(allowance))
    accepted = max(progress.watched_seconds, accepted)  # never goes down
    if duration:
        accepted = min(accepted, duration)

    progress.watched_seconds = accepted
    progress.position_seconds = _clamp(position_seconds, 0, duration) if duration else max(0, position_seconds)
    progress.duration_seconds = duration
    progress.completion_percent = min(100, int(100 * accepted / duration)) if duration else progress.completion_percent
    progress.last_reported_at = now
    if progress.completed_at is None and duration and progress.completion_percent >= lesson.completion_threshold:
        progress.completed_at = now
        progress.completed_via = "player"
    progress.save()

    # Taking part in a course means being enrolled in it (My learning lists enrollments).
    Enrollment.objects.get_or_create(
        learner=user, course=lesson.course,
        defaults={"source": Enrollment.Source.PURCHASE if lesson.course.is_paid else Enrollment.Source.FREE},
    )
    return progress
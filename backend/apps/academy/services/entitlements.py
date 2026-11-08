"""Who may open a paid course. The ONLY place that answers "is this learner entitled?": the views never guess from a request."""
from django.db.models import Q
from django.utils import timezone

from ..models import CourseEntitlement


def active_entitlement(user, course):
    """The learner's current entitlement to `course`, or None. Revoked, not-yet-started and expired ones do not count."""
    if not (user and user.is_authenticated and user.is_active):
        return None
    now = timezone.now()
    return (
        CourseEntitlement.objects.filter(learner=user, course=course, status=CourseEntitlement.Status.ACTIVE, starts_at__lte=now)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .first()
    )


def has_access(user, course):
    return active_entitlement(user, course) is not None
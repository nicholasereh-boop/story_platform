"""Atomic counter helpers shared by likes and comments."""
from django.db.models import F, IntegerField, Value
from django.db.models.functions import Greatest


def adjust_story_counter(story_id, field, delta):
    """Add `delta` to Story.<field> in ONE SQL UPDATE (no read-modify-write, so concurrent requests never lose a count).

    Greatest(..., 0) means a drifted counter can never go negative (PositiveIntegerField would reject it);
    `manage.py recount_engagement` repairs any drift.
    """
    if not delta:
        return
    from apps.stories.models import Story  # imported here: stories imports nothing from core.counters

    Story.objects.filter(pk=story_id).update(
        **{field: Greatest(F(field) + delta, Value(0), output_field=IntegerField())}
    )

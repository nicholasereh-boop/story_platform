from django.conf import settings
from django.db import models
from django.db.models import Q


class Like(models.Model):
    """One person likes one story, either as a logged-in user or as an anonymous visitor.

    A like belongs to EXACTLY ONE of the two (database check):
      * `user`        a logged-in reader;
      * `visitor_id`  a random token kept in that browser's session (see views.visitor_id_for). It identifies a browser
                      and nothing else: it is not derived from an IP address, name or e-mail, and it never leaves the server.
    The database itself guarantees one like per person per story (a partial unique constraint for each kind).
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="likes")
    visitor_id = models.CharField(max_length=43, null=True, blank=True, db_index=True)
    story = models.ForeignKey("stories.Story", on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "story"], condition=Q(user__isnull=False), name="like_unique_user_story"),
            models.UniqueConstraint(fields=["visitor_id", "story"], condition=Q(visitor_id__isnull=False), name="like_unique_visitor_story"),
            models.CheckConstraint(
                condition=(Q(user__isnull=False, visitor_id__isnull=True) | Q(user__isnull=True, visitor_id__isnull=False)),
                name="like_user_xor_visitor",
            ),
        ]
        indexes = [models.Index(fields=["story", "created_at"], name="like_story_created_idx")]

    def __str__(self):
        who = f"user {self.user_id}" if self.user_id else "a visitor"
        return f"{who} likes {self.story_id}"

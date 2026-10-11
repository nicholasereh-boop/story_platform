from django.conf import settings
from django.db import models


class Like(models.Model):
    """One reader likes one story. The database itself guarantees a reader can like a story only once."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    story = models.ForeignKey("stories.Story", on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "story"], name="like_unique_user_story")]
        indexes = [models.Index(fields=["story", "created_at"], name="like_story_created_idx")]

    def __str__(self):
        return f"{self.user_id} likes {self.story_id}"

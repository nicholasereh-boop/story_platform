from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditImmutableError(Exception):
    """Raised by any attempt to change or delete an audit entry."""


class AuditQuerySet(models.QuerySet):
    """Refuses bulk updates and deletes. The only two sanctioned mutations are named, narrow and explicit:
    redact_actor_labels() (privacy: an erased account's name leaves old entries) and purge_before() (retention)."""

    def update(self, **kwargs):
        raise AuditImmutableError("Audit log entries cannot be updated.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise AuditImmutableError("Audit log entries cannot be updated.")

    def delete(self):
        raise AuditImmutableError("Audit log entries cannot be deleted (retention uses purge_before()).")

    def redact_actor_labels(self, label="Deleted user"):
        return models.QuerySet.update(self, actor_label=label)

    def purge_before(self, cutoff):
        """Retention only: remove entries older than `cutoff`. Returns how many were removed."""
        deleted, _ = models.QuerySet.delete(self.filter(created_at__lt=cutoff))
        return deleted


class AuditLog(models.Model):
    """One administrative or security event. Append-only: there is no way to edit or remove one through the app."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_label = models.CharField(max_length=120, blank=True)  # the actor's display name AT THE TIME ("system" for jobs)
    action = models.CharField(max_length=60)  # one of audit.actions.ACTIONS
    object_type = models.CharField(max_length=40, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    # Ids, titles, changed field NAMES, old and new status. Never passwords, tokens, story bodies or comment text.
    metadata = models.JSONField(default=dict, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)  # keyed HMAC of the client IP; the raw IP is never stored
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = AuditQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["action", "created_at"], name="audit_action_created_idx"),
            models.Index(fields=["object_type", "object_id"], name="audit_object_idx"),
            models.Index(fields=["actor", "created_at"], name="audit_actor_created_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AuditImmutableError("Audit log entries cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditImmutableError("Audit log entries cannot be deleted.")

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} by {self.actor_label or 'system'}"

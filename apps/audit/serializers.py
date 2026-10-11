from rest_framework import serializers

from .actions import ACTIONS
from .models import AuditLog

DELETED_LABEL = "Deleted user"


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only. The raw IP is never stored; only a short reference of its keyed hash is shown (to spot "same address")."""

    actor_label = serializers.SerializerMethodField()
    action_label = serializers.SerializerMethodField()
    ip_ref = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "created_at", "actor", "actor_label", "action", "action_label", "object_type", "object_id", "metadata", "ip_ref"]
        read_only_fields = fields

    def get_actor_label(self, obj):
        actor = obj.actor
        if actor is not None and actor.email.endswith("@invalid.invalid"):
            return DELETED_LABEL  # an erased account never shows its old name
        return obj.actor_label or "system"

    def get_action_label(self, obj):
        return ACTIONS.get(obj.action, obj.action)

    def get_ip_ref(self, obj):
        return obj.ip_hash[:12]

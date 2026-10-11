from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Append-only audit trail of administrative and security-relevant events (Phase 10)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"

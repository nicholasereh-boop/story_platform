"""GET /api/v1/admin/audit-logs/ : read-only, staff only. There is deliberately no create, update or delete endpoint."""

from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import generics, serializers

from apps.core.permissions import IsStaffUser

from .models import AuditLog
from .serializers import AuditLogSerializer


def _date_param(params, name):
    raw = params.get(name)
    if not raw:
        return None
    parsed = parse_date(raw)
    if parsed is None:
        raise serializers.ValidationError({name: ["Use the format YYYY-MM-DD."], "detail": [f"Invalid date for '{name}'."]})
    return parsed


class AuditLogListView(generics.ListAPIView):
    """Filters: action (exact, or "story.*" for a family), actor (user id), object_type, object_id, from, to (dates), q."""

    permission_classes = [IsStaffUser]
    serializer_class = AuditLogSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        params = self.request.query_params
        qs = AuditLog.objects.select_related("actor").order_by("-created_at", "-id")
        action = (params.get("action") or "").strip()
        if action:
            qs = qs.filter(action__startswith=action[:-1]) if action.endswith("*") else qs.filter(action=action)
        actor = params.get("actor")
        if actor:
            if not actor.isdigit():
                raise serializers.ValidationError({"actor": ["Use a user id."], "detail": ["Invalid actor."]})
            qs = qs.filter(actor_id=int(actor))
        if params.get("object_type"):
            qs = qs.filter(object_type=params["object_type"])
        if params.get("object_id"):
            qs = qs.filter(object_id=params["object_id"])
        start, end = _date_param(params, "from"), _date_param(params, "to")
        if start:
            qs = qs.filter(created_at__date__gte=start)
        if end:
            qs = qs.filter(created_at__date__lte=end)
        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(actor_label__icontains=q) | Q(action__icontains=q) | Q(object_type__icontains=q) | Q(object_id__iexact=q)
            )
        return qs

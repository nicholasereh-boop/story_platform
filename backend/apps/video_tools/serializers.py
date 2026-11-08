from rest_framework import serializers

from .models import DownloadJob
from .services import providers
from .services.url_validation import parse_video_url, InvalidVideoUrl


class UrlSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=2048, trim_whitespace=False)

    def validate_url(self, value):
        try:
            return parse_video_url(value)
        except InvalidVideoUrl as exc:
            raise serializers.ValidationError(exc.message)


class DownloadRequestSerializer(UrlSerializer):
    format = serializers.CharField(max_length=20, required=False, allow_blank=True)
    authorization_confirmed = serializers.BooleanField(required=False, default=False)

    def validate_authorization_confirmed(self, value):
        if value is not True:
            raise serializers.ValidationError("Confirm that you own this video or have permission to download it.")
        return value

    def validate(self, attrs):
        if "authorization_confirmed" not in self.initial_data:
            raise serializers.ValidationError({"authorization_confirmed": ["Confirm that you own this video or have permission to download it."]})
        return attrs


def capability_payload(cap):
    return {"available": cap.available, "reason": cap.reason, "method": cap.method, "formats": cap.formats}


def inspect_payload(parsed):
    cap = providers.capability_for(parsed.provider)
    return {
        "provider": parsed.provider,
        "provider_label": cap.label,
        "content_kind": parsed.content_kind,
        "content_id": parsed.content_id,
        "canonical_url": parsed.canonical_url,
        "needs_resolution": parsed.needs_resolution,
        "download": capability_payload(cap),
        "guidance": providers.GUIDANCE[parsed.provider],
        "notice": providers.WATERMARK_NOTE,
    }


class JobSerializer(serializers.ModelSerializer):
    artifact = serializers.SerializerMethodField()
    provider_label = serializers.SerializerMethodField()

    class Meta:
        model = DownloadJob
        fields = ["id", "provider", "provider_label", "source_url", "format_key", "status", "error_code", "error_message",
                  "created_at", "started_at", "finished_at", "artifact"]

    def get_provider_label(self, obj):
        from .services.url_validation import LABELS
        return LABELS.get(obj.provider, obj.provider)

    def get_artifact(self, obj):
        art = getattr(obj, "artifact", None)
        if art is None or art.deleted_at:
            return None
        return {"filename": art.filename, "size_bytes": art.size_bytes, "content_type": art.content_type, "expires_at": art.expires_at}

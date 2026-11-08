from rest_framework import serializers

from .models import NewsRightsRecord, NewsSource


class SourceWriteSerializer(serializers.ModelSerializer):
    """Fields staff may set. approval_state, reviewer and timestamps change only through the approve / suspend / reject actions."""

    class Meta:
        model = NewsSource
        fields = [
            "name", "slug", "source_type", "website_url", "terms_url", "adapter", "feed_url", "allows_full_text",
            "allows_commercial_use", "attribution_template", "evidence_ref", "renewal_contact", "poll_interval_minutes",
            "max_items_per_poll", "daily_request_quota", "notes",
        ]

    def validate(self, attrs):
        instance = self.instance
        adapter = attrs.get("adapter", instance.adapter if instance else "")
        feed_url = attrs.get("feed_url", instance.feed_url if instance else "")
        if adapter and not feed_url:
            raise serializers.ValidationError({"feed_url": "A feed address is needed for this adapter."})
        source_type = attrs.get("source_type", instance.source_type if instance else NewsSource.SourceType.LICENSED)
        if source_type == NewsSource.SourceType.METADATA_ONLY:
            attrs["allows_full_text"] = False
        return attrs

    def validate_feed_url(self, value):
        if value and not value.lower().startswith("https://"):
            raise serializers.ValidationError("Feeds must use https.")
        return value

    def validate_poll_interval_minutes(self, value):
        if value < 15:
            raise serializers.ValidationError("Poll no more often than every 15 minutes.")
        return value

    def validate_max_items_per_poll(self, value):
        if not 1 <= value <= 100:
            raise serializers.ValidationError("Choose between 1 and 100 items per poll.")
        return value


class RightsWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsRightsRecord
        fields = [
            "title", "licence", "licence_version", "licence_url", "basis", "allows_full_text", "allows_commercial_use",
            "allows_modification", "requires_attribution", "requires_counter", "allows_caching", "allows_archive",
            "retention_days", "restrictions", "effective_from", "effective_until", "evidence_url", "evidence_note",
        ]

    def validate(self, attrs):
        start = attrs.get("effective_from", self.instance.effective_from if self.instance else None)
        end = attrs.get("effective_until", self.instance.effective_until if self.instance else None)
        if start and end and end <= start:
            raise serializers.ValidationError({"effective_until": "The end date must be after the start date."})
        return attrs


def source_data(source):
    return {
        "id": source.pk, "name": source.name, "slug": source.slug, "source_type": source.source_type,
        "website_url": source.website_url, "terms_url": source.terms_url, "adapter": source.adapter, "feed_url": source.feed_url,
        "is_active": source.is_active, "approval_state": source.approval_state, "allows_full_text": source.allows_full_text,
        "allows_commercial_use": source.allows_commercial_use, "attribution_template": source.attribution_template,
        "evidence_ref": source.evidence_ref, "renewal_contact": source.renewal_contact,
        "poll_interval_minutes": source.poll_interval_minutes, "max_items_per_poll": source.max_items_per_poll,
        "daily_request_quota": source.daily_request_quota, "notes": source.notes,
        "reviewed_at": source.reviewed_at, "created_at": source.created_at, "updated_at": source.updated_at,
    }


def rights_data(record):
    from .services import rights

    return {
        "id": record.pk, "source": record.source_id, "title": record.title, "licence": record.licence,
        "licence_version": record.licence_version, "licence_url": record.licence_url, "basis": record.basis,
        "allows_full_text": record.allows_full_text, "allows_commercial_use": record.allows_commercial_use,
        "allows_modification": record.allows_modification, "requires_attribution": record.requires_attribution,
        "requires_counter": record.requires_counter, "allows_caching": record.allows_caching,
        "allows_archive": record.allows_archive, "retention_days": record.retention_days, "restrictions": record.restrictions,
        "effective_from": record.effective_from, "effective_until": record.effective_until,
        "evidence_url": record.evidence_url, "evidence_note": record.evidence_note, "status": record.status,
        "in_force": rights.record_in_force(record), "reviewed_at": record.reviewed_at,
        "revoked_at": record.revoked_at, "revoked_reason": record.revoked_reason, "created_at": record.created_at,
    }

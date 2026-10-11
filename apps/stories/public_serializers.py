"""Serializers for the PUBLIC API. Deliberately separate from the admin ones.

Rule: every field is listed explicitly (an allowlist). Nothing private is ever exposed here: no status,
scheduled_at, user ids or emails, view counts, revisions or search_text. (like_count / comment_count are
public by design since Phase 8.) Adding a model field never leaks it by accident.
"""
import math

from rest_framework import serializers

from .content import plain_text, resolve_media
from .models import Category, Story, Tag
from .serializers import author_name

WORDS_PER_MINUTE = 200


def reading_minutes(text):
    """Estimated reading time in whole minutes (at least 1 for any text, 0 for none)."""
    words = len((text or "").split())
    return max(1, math.ceil(words / WORDS_PER_MINUTE)) if words else 0


class PublicCoverSerializer(serializers.Serializer):
    """The cover image without its internal id."""

    url = serializers.SerializerMethodField()
    alt_text = serializers.CharField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()

    def get_url(self, obj):
        return obj.file.url if obj.file else None


class PublicCategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["name", "slug"]


class PublicTagBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["name", "slug"]


class PublicCategorySerializer(serializers.ModelSerializer):
    story_count = serializers.IntegerField(read_only=True)  # annotated with PUBLIC stories only

    class Meta:
        model = Category
        fields = ["name", "slug", "description", "story_count"]


class PublicTagSerializer(serializers.ModelSerializer):
    story_count = serializers.IntegerField(read_only=True)  # annotated with PUBLIC stories only

    class Meta:
        model = Tag
        fields = ["name", "slug", "story_count"]


class PublicStoryListSerializer(serializers.ModelSerializer):
    cover = PublicCoverSerializer(source="cover_image", read_only=True)
    categories = PublicCategoryBriefSerializer(many=True, read_only=True)
    tags = PublicTagBriefSerializer(many=True, read_only=True)
    author = serializers.SerializerMethodField()
    reading_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            "id", "title", "slug", "excerpt", "cover", "categories", "tags", "author",
            "published_at", "reading_minutes", "is_featured", "like_count", "comment_count",
        ]

    def get_author(self, obj):
        return author_name(obj.created_by)

    def get_reading_minutes(self, obj):
        # search_text is the plain text of the story (kept by Story.save), so lists never have to load content_json.
        return reading_minutes(obj.search_text)


class PublicStorySerializer(PublicStoryListSerializer):
    seo_title = serializers.SerializerMethodField()
    seo_description = serializers.SerializerMethodField()
    canonical_path = serializers.SerializerMethodField()

    class Meta(PublicStoryListSerializer.Meta):
        fields = PublicStoryListSerializer.Meta.fields + [
            "content_json", "seo_title", "seo_description", "canonical_path", "updated_at",
        ]

    def get_seo_title(self, obj):
        return obj.seo_title or obj.title

    def get_seo_description(self, obj):
        return obj.seo_description or obj.excerpt

    def get_canonical_path(self, obj):
        return f"/stories/{obj.slug}"

    def get_reading_minutes(self, obj):
        return reading_minutes(plain_text(obj.content_json))  # the full text for the detail page

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:  # only logged-in readers get this key
            from apps.reactions.models import Like

            data["liked_by_me"] = Like.objects.filter(user=user, story=instance).exists()
        data["content_json"] = resolve_media(instance.content_json)  # image nodes get src/width/height, as in admin
        return data

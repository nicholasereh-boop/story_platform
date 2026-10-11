import re

from rest_framework import serializers

from apps.media.models import MediaAsset
from apps.media.serializers import MediaCoverSerializer

from .content import asset_ids, clean_content, resolve_media
from .models import Category, Story, StoryRevision, Tag

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def author_name(user):
    """Display name without extra queries when created_by__profile was select_related."""
    if user is None:
        return None
    profile = getattr(user, "profile", None)  # missing profile -> AttributeError -> None
    return profile.display_name if profile and profile.display_name else user.email.split("@")[0]


# ---------------- categories & tags ----------------
class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class TagBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class _TaxonomySerializer(serializers.ModelSerializer):
    story_count = serializers.SerializerMethodField()

    def get_story_count(self, obj):
        count = getattr(obj, "story_count", None)  # annotated in list views, avoids N+1
        return count if count is not None else obj.stories.count()

    def validate_name(self, value):
        value = value.strip()
        clash = self.Meta.model.objects.filter(name__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("That name is already in use.")
        return value


class CategorySerializer(_TaxonomySerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "story_count", "created_at"]
        read_only_fields = ["slug", "created_at"]  # slug is generated once and then stays stable


class TagSerializer(_TaxonomySerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "story_count"]
        read_only_fields = ["slug"]


# ---------------- stories ----------------
class AdminStoryListSerializer(serializers.ModelSerializer):
    """Light version for lists: no content_json."""

    categories = CategoryBriefSerializer(many=True, read_only=True)
    tags = TagBriefSerializer(many=True, read_only=True)
    cover = MediaCoverSerializer(source="cover_image", read_only=True)
    author = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            "id", "title", "slug", "excerpt", "status", "is_featured", "cover", "categories", "tags", "author",
            "published_at", "scheduled_at", "created_at", "updated_at", "view_count", "like_count", "comment_count",
        ]

    def get_author(self, obj):
        return author_name(obj.created_by)


class AdminStorySerializer(serializers.ModelSerializer):
    """Full story. status, publish dates and counters are read-only: only the action endpoints change them."""

    content_json = serializers.JSONField(required=False)
    slug = serializers.CharField(max_length=220, required=False)
    excerpt = serializers.CharField(max_length=500, required=False, allow_blank=True)
    category_ids = serializers.PrimaryKeyRelatedField(source="categories", many=True, queryset=Category.objects.all(), required=False)
    tag_ids = serializers.PrimaryKeyRelatedField(source="tags", many=True, queryset=Tag.objects.all(), required=False)
    cover_image = serializers.PrimaryKeyRelatedField(
        queryset=MediaAsset.objects.all(), allow_null=True, required=False,
        error_messages={"does_not_exist": "That image does not exist.", "incorrect_type": "That image does not exist."},
    )
    cover = MediaCoverSerializer(source="cover_image", read_only=True)
    categories = CategoryBriefSerializer(many=True, read_only=True)
    tags = TagBriefSerializer(many=True, read_only=True)
    author = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            "id", "title", "slug", "excerpt", "content_json", "cover_image", "cover", "category_ids", "tag_ids", "categories", "tags",
            "is_featured", "seo_title", "seo_description", "status", "published_at", "scheduled_at",
            "author", "view_count", "like_count", "comment_count", "created_at", "updated_at",
        ]
        read_only_fields = [
            "status", "published_at", "scheduled_at", "view_count", "like_count", "comment_count", "created_at", "updated_at",
        ]

    def get_author(self, obj):
        return author_name(obj.created_by)

    def validate_slug(self, value):
        value = value.strip()
        if not SLUG_RE.match(value):
            raise serializers.ValidationError("Use lowercase letters, digits and single hyphens only.")
        clash = Story.objects.filter(slug=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("Another story already uses this slug.")
        return value

    def validate_content_json(self, value):
        cleaned = clean_content(value)  # the only way content reaches the database
        ids = asset_ids(cleaned)
        if ids:
            existing = set(MediaAsset.objects.filter(pk__in=ids).values_list("pk", flat=True))
            missing = sorted(ids - existing)
            if missing:
                raise serializers.ValidationError("These images are not in the media library: " + ", ".join(map(str, missing)) + ".")
        return cleaned

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["content_json"] = resolve_media(instance.content_json)  # adds read-only src/width/height to images
        return data

    def create(self, validated_data):
        categories = validated_data.pop("categories", None)
        tags = validated_data.pop("tags", None)
        story = Story(**validated_data)  # status defaults to draft
        story.save()
        if categories is not None:
            story.categories.set(categories)
        if tags is not None:
            story.tags.set(tags)
        return story

    def update(self, instance, validated_data):
        categories = validated_data.pop("categories", None)
        tags = validated_data.pop("tags", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if categories is not None:
            instance.categories.set(categories)
        if tags is not None:
            instance.tags.set(tags)
        return instance


class RevisionSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    content_json = serializers.SerializerMethodField()

    class Meta:
        model = StoryRevision
        fields = ["id", "revision_number", "title", "excerpt", "content_json", "author", "created_at"]

    def get_author(self, obj):
        return author_name(obj.created_by)

    def get_content_json(self, obj):
        return resolve_media(obj.content_json)


class ScheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()

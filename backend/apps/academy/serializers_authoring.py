"""Staff-side serializers: create and change courses and lessons (nothing here is ever shown to learners)."""
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from apps.core.text import clean_plain_text, strip_unsafe_chars
from apps.media.models import MediaAsset
from apps.stories.content import youtube_id

from .models import Course, Lesson
from .services import courses as course_service


def thumbnail_data(asset):
    if not asset or not asset.file:
        return None
    return {"id": asset.pk, "url": asset.file.url, "width": asset.width, "height": asset.height, "alt_text": asset.alt_text}


def course_admin_data(course):
    """The staff view of a course. Counts come from annotations when the list view provides them, else from queries."""
    lesson_total = getattr(course, "lesson_total", None)
    if lesson_total is None:
        lesson_total = course.lessons.count()
    published = getattr(course, "published_lessons", None)
    if published is None:
        published = course.lessons.filter(is_published=True).count()
    learners = getattr(course, "learner_total", None)
    if learners is None:
        learners = course.enrollments.count()
    return {
        "id": course.pk, "slug": course.slug, "title": course.title, "summary": course.summary, "description": course.description,
        "level": course.level, "category": course.category, "thumbnail": thumbnail_data(course.thumbnail),
        "status": course.status, "access_type": course.access_type, "price": f"{course.price:.2f}", "currency": course.currency,
        "video_rights_confirmed": bool(course.video_rights_confirmed_at), "lesson_count": lesson_total, "published_lesson_count": published,
        "learner_count": learners, "created_at": course.created_at, "updated_at": course.updated_at, "published_at": course.published_at,
        "locked_type": course_service.has_learner_activity(course) if course.pk else False,
    }


def lesson_admin_data(lesson):
    return {
        "id": lesson.pk, "course_id": lesson.course_id, "title": lesson.title, "description": lesson.description, "position": lesson.position,
        "youtube_id": lesson.youtube_id, "duration_seconds": lesson.duration_seconds, "is_intro": lesson.is_intro, "is_preview": lesson.is_preview,
        "requires_comment_to_unlock_next": lesson.requires_comment_to_unlock_next, "completion_threshold": lesson.completion_threshold,
        "is_published": lesson.is_published, "updated_at": lesson.updated_at,
    }


class CourseWriteSerializer(serializers.Serializer):
    """Create / update. Status, creator and publishing dates can NOT be set here (they have their own actions)."""

    title = serializers.CharField(max_length=160)
    slug = serializers.CharField(max_length=90, required=False, allow_blank=True)
    summary = serializers.CharField(max_length=300, required=False, allow_blank=True)
    description = serializers.CharField(max_length=20000, required=False, allow_blank=True)
    level = serializers.ChoiceField(choices=Course.Level.choices, required=False)
    category = serializers.CharField(max_length=60, required=False, allow_blank=True)
    access_type = serializers.ChoiceField(choices=Course.Access.choices, required=False)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=Decimal("0"))
    thumbnail_id = serializers.IntegerField(required=False, allow_null=True)
    video_rights_confirmed = serializers.BooleanField(required=False)

    def validate_title(self, value):
        return clean_plain_text(value, max_length=160, allow_blank=False)

    def validate_summary(self, value):
        return clean_plain_text(value, max_length=300)

    def validate_category(self, value):
        return clean_plain_text(value, max_length=60)

    def validate_description(self, value):
        return strip_unsafe_chars(value, multiline=True)  # plain text, always shown as text

    def validate_slug(self, value):
        value = value.strip().lower()
        if value and not course_service.valid_custom_slug(value):
            raise serializers.ValidationError("Use lowercase letters, numbers and single dashes, with at least one letter.")
        if value:
            qs = Course.objects.filter(slug=value)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("That address is already taken.")
        return value

    def validate(self, attrs):
        instance = self.instance
        access = attrs.get("access_type", instance.access_type if instance else Course.Access.FREE)
        price = attrs.get("price", instance.price if instance else Decimal("0"))
        if access == Course.Access.FREE:
            attrs["price"] = Decimal("0")
        else:
            if price <= 0:
                raise serializers.ValidationError({"price": ["A paid course needs a price above 0."]})
            if price > Decimal(str(settings.ACADEMY_MAX_PRICE)):
                raise serializers.ValidationError({"price": [f"The highest price allowed is {settings.ACADEMY_MAX_PRICE} {settings.ACADEMY_CURRENCY}."]})
        if instance is not None and access != instance.access_type and course_service.has_learner_activity(instance):
            raise serializers.ValidationError({"access_type": ["This course already has learners or orders, so it cannot change between free and paid. Archive it and create a new course instead."]})
        thumb = attrs.get("thumbnail_id")
        if thumb is not None and not MediaAsset.objects.filter(pk=thumb).exists():
            raise serializers.ValidationError({"thumbnail_id": ["That image does not exist."]})
        return attrs

    def save(self, creator=None, instance=None):
        data = dict(self.validated_data)
        slug = data.pop("slug", "")
        rights = data.pop("video_rights_confirmed", None)
        thumb_given = "thumbnail_id" in data
        thumb_id = data.pop("thumbnail_id", None)
        if instance is None:
            instance = Course(creator=creator, currency=settings.ACADEMY_CURRENCY)
            instance.slug = slug or course_service.make_slug(data.get("title", "course"))
        elif slug and instance.status != Course.Status.PUBLISHED:
            instance.slug = slug  # the address of a published course never changes
        for key, value in data.items():
            setattr(instance, key, value)
        if thumb_given:
            instance.thumbnail = MediaAsset.objects.filter(pk=thumb_id).first() if thumb_id else None
        if rights is True and not instance.video_rights_confirmed_at:
            instance.video_rights_confirmed_at = timezone.now()
        elif rights is False:
            instance.video_rights_confirmed_at = None
        instance.save()
        return instance


class LessonWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=160)
    description = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    youtube_url = serializers.CharField(max_length=300, required=False, allow_blank=True)  # a YouTube link or the 11-character id
    duration_seconds = serializers.IntegerField(required=False, min_value=0, max_value=86400)
    is_intro = serializers.BooleanField(required=False)
    is_preview = serializers.BooleanField(required=False)
    requires_comment_to_unlock_next = serializers.BooleanField(required=False)
    completion_threshold = serializers.IntegerField(required=False, min_value=10, max_value=100)
    is_published = serializers.BooleanField(required=False)

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course or (self.instance.course if self.instance else None)

    def validate_title(self, value):
        return clean_plain_text(value, max_length=160, allow_blank=False)

    def validate_description(self, value):
        return strip_unsafe_chars(value, multiline=True)

    def validate_youtube_url(self, value):
        value = value.strip()
        if not value:
            return ""
        vid = youtube_id(value)
        if not vid:
            raise serializers.ValidationError("Enter a YouTube link (https://www.youtube.com/watch?v=... or https://youtu.be/...).")
        return vid  # only the 11-character id is ever kept (never HTML, never a URL)

    def validate(self, attrs):
        instance = self.instance
        vid = attrs.get("youtube_url", instance.youtube_id if instance else "")
        publish = attrs.get("is_published", instance.is_published if instance else False)
        if publish and not vid:
            raise serializers.ValidationError({"is_published": ["Add a YouTube video before publishing this lesson."]})
        intro = attrs.get("is_intro", instance.is_intro if instance else False)
        if intro:
            others = Lesson.objects.filter(course=self.course, is_intro=True)
            if instance is not None:
                others = others.exclude(pk=instance.pk)
            if others.exists():
                raise serializers.ValidationError({"is_intro": ["This course already has an introduction lesson."]})
            attrs["requires_comment_to_unlock_next"] = False  # the introduction never gates the next lesson
        return attrs

    def save(self):
        data = dict(self.validated_data)
        vid = data.pop("youtube_url", None)
        instance = self.instance
        if instance is None:
            instance = Lesson(
                course=self.course, position=course_service.next_position(self.course),
                requires_comment_to_unlock_next=settings.ACADEMY_COMMENT_GATE_DEFAULT,
                completion_threshold=settings.ACADEMY_DEFAULT_COMPLETION_THRESHOLD,
            )
        for key, value in data.items():
            setattr(instance, key, value)
        if vid is not None:
            instance.youtube_id = vid
        if instance.is_intro:
            instance.requires_comment_to_unlock_next = False
        instance.save()
        return instance
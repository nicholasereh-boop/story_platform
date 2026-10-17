from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsStaffUser

from .content import clean_content, has_content
from .models import Category, Story, StoryRevision, Tag
from .serializers import (
    AdminStoryListSerializer,
    AdminStorySerializer,
    CategorySerializer,
    RevisionSerializer,
    ScheduleSerializer,
    TagSerializer,
)
from .services import create_revision, publish_due

ORDERINGS = {"title", "-title", "created_at", "-created_at", "updated_at", "-updated_at", "published_at", "-published_at"}


def story_queryset():
    """One query for stories, one for categories, one for tags; author comes via select_related."""
    return Story.objects.select_related("created_by__profile", "cover_image").prefetch_related("categories", "tags")


# ---------------------------------------------------------------- stories
class AdminStoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsStaffUser]

    def get_serializer_class(self):
        return AdminStorySerializer if self.request.method == "POST" else AdminStoryListSerializer

    def get_queryset(self):
        publish_due()
        params = self.request.query_params
        qs = story_queryset()
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("q"):
            qs = qs.filter(Q(title__icontains=params["q"]) | Q(slug__icontains=params["q"]))
        if params.get("category"):
            qs = qs.filter(categories__slug=params["category"])
        if params.get("tag"):
            qs = qs.filter(tags__slug=params["tag"])
        if params.get("featured") in ("1", "true"):
            qs = qs.filter(is_featured=True)
        ordering = params.get("ordering")
        if ordering in ORDERINGS:
            return qs.order_by(ordering, "-id")
        return qs.order_by("-updated_at", "-id")

    def perform_create(self, serializer):
        user = self.request.user
        story = serializer.save(created_by=user, updated_by=user)
        create_revision(story, user)  # revision 1


class AdminStoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = AdminStorySerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]  # partial updates only

    def get_queryset(self):
        publish_due()
        return story_queryset()

    def perform_update(self, serializer):
        user = self.request.user
        story = serializer.save(updated_by=user)
        autosave = self.request.query_params.get("autosave") == "1"
        create_revision(story, user, min_interval_minutes=10 if autosave else 0)


class StoryActionView(APIView):
    """Base for publish / unpublish / archive / schedule. Subclasses implement apply()."""

    permission_classes = [IsStaffUser]

    def apply(self, request, story):
        raise NotImplementedError

    def post(self, request, pk, *args, **kwargs):
        publish_due()
        story = get_object_or_404(story_queryset(), pk=pk)
        self.apply(request, story)
        story.updated_by = request.user
        story.save()
        create_revision(story, request.user)  # no-op unless the content changed
        return Response(AdminStorySerializer(story).data)


class PublishView(StoryActionView):
    def apply(self, request, story):
        if not story.title.strip():
            raise serializers.ValidationError({"detail": ["Give the story a title before publishing."]})
        if not has_content(story.content_json):
            raise serializers.ValidationError({"detail": ["The story is empty. Add some text, an image or a video first."]})
        story.status = Story.Status.PUBLISHED
        story.published_at = story.published_at or timezone.now()
        story.scheduled_at = None


class UnpublishView(StoryActionView):
    def apply(self, request, story):
        story.status = Story.Status.DRAFT


class ArchiveView(StoryActionView):
    def apply(self, request, story):
        story.status = Story.Status.ARCHIVED


class ScheduleView(StoryActionView):
    def apply(self, request, story):
        serializer = ScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        when = serializer.validated_data["scheduled_at"]
        if when <= timezone.now():
            raise serializers.ValidationError({"scheduled_at": ["Choose a time in the future."]})
        story.status = Story.Status.SCHEDULED
        story.scheduled_at = when
        story.published_at = None


class AdminRevisionListView(generics.ListAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = RevisionSerializer

    def get_queryset(self):
        story = get_object_or_404(Story, pk=self.kwargs["pk"])
        return story.revisions.select_related("created_by__profile")


class RestoreRevisionView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request, pk, revision_id, *args, **kwargs):
        story = get_object_or_404(story_queryset(), pk=pk)
        revision = get_object_or_404(StoryRevision, pk=revision_id, story=story)
        story.title = revision.title
        story.excerpt = revision.excerpt
        story.content_json = clean_content(revision.content_json)  # never trust stored data blindly
        story.updated_by = request.user
        story.save()
        create_revision(story, request.user)  # the restore itself becomes a new revision
        return Response(AdminStorySerializer(story).data)


# ---------------------------------------------------------------- categories & tags
class AdminCategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = Category.objects.annotate(story_count=Count("stories"))


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = CategorySerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]
    queryset = Category.objects.annotate(story_count=Count("stories"))  # deleting only unlinks stories


class AdminTagListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = TagSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Tag.objects.annotate(story_count=Count("stories"))
        q = self.request.query_params.get("q")  # autocomplete
        return qs.filter(name__icontains=q) if q else qs


class AdminTagDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = TagSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]
    queryset = Tag.objects.annotate(story_count=Count("stories"))

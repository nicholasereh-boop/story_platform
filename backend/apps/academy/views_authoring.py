"""Staff endpoints for authoring courses and lessons (docs/ARCHITECTURE.md: /academy/admin/...). Every one of them checks
is_staff (and the two-step code) on the server; the React admin pages are only a convenience."""
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import service as audit
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsStaffUser

from .errors import Conflict
from .models import Course, Lesson
from .permissions import AcademyEnabled
from .serializers_authoring import CourseWriteSerializer, LessonWriteSerializer, course_admin_data, lesson_admin_data
from .services import courses as course_service


class StaffView(APIView):
    permission_classes = [AcademyEnabled, IsStaffUser]
    parser_classes = [JSONParser]


def _course_or_404(pk):
    return get_object_or_404(Course.objects.select_related("thumbnail"), pk=pk)


class AdminCourseListCreateView(StaffView):
    def get(self, request, **kwargs):
        qs = Course.objects.select_related("thumbnail").annotate(
            lesson_total=Count("lessons", distinct=True),
            published_lessons=Count("lessons", filter=Q(lessons__is_published=True), distinct=True),
            learner_total=Count("enrollments", distinct=True),
        ).order_by("-updated_at", "-id")
        status_ = request.query_params.get("status")
        if status_ in Course.Status.values:
            qs = qs.filter(status=status_)
        access = request.query_params.get("access")
        if access in Course.Access.values:
            qs = qs.filter(access_type=access)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(slug__icontains=q))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([course_admin_data(c) for c in page])

    def post(self, request, **kwargs):
        serializer = CourseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            course = serializer.save(creator=request.user)
            audit.log(request, "academy.course_create", course, title=course.title, access=course.access_type)
        return Response(course_admin_data(course), status=201)


class AdminCourseDetailView(StaffView):
    def get(self, request, pk, **kwargs):
        return Response(course_admin_data(_course_or_404(pk)))

    def patch(self, request, pk, **kwargs):
        course = _course_or_404(pk)
        before = {"price": f"{course.price:.2f}", "access": course.access_type}
        serializer = CourseWriteSerializer(course, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            course = serializer.save(instance=course)
            audit.log(request, "academy.course_update", course, title=course.title, price_before=before["price"], price_after=f"{course.price:.2f}",
                      access_before=before["access"], access_after=course.access_type)
        return Response(course_admin_data(course))

    def delete(self, request, pk, **kwargs):
        course = _course_or_404(pk)
        if course_service.has_learner_activity(course):
            raise Conflict("This course already has learners or orders. Archive it instead of deleting it.")
        with transaction.atomic():
            audit.log(request, "academy.course_delete", course, title=course.title)
            course.delete()
        return Response(status=204)


class AdminCourseStatusView(StaffView):
    """POST /academy/admin/courses/<id>/publish|unpublish|archive/"""

    def post(self, request, pk, action, **kwargs):
        course = _course_or_404(pk)
        if action == "publish":
            problems = course_service.publish_problems(course)
            if problems:
                raise serializers.ValidationError({"publish": problems})
            course.status = Course.Status.PUBLISHED
            course.published_at = course.published_at or timezone.now()
            event = "academy.course_publish"
        elif action == "unpublish":
            course.status = Course.Status.DRAFT
            event = "academy.course_unpublish"
        elif action == "archive":
            course.status = Course.Status.ARCHIVED
            event = "academy.course_archive"
        else:
            raise serializers.ValidationError({"action": ["Unknown action."]})
        with transaction.atomic():
            course.save(update_fields=["status", "published_at", "updated_at"])
            audit.log(request, event, course, title=course.title)
        return Response(course_admin_data(course))


class AdminLessonListCreateView(StaffView):
    def get(self, request, pk, **kwargs):
        course = _course_or_404(pk)
        return Response([lesson_admin_data(lesson) for lesson in course.lessons.all()])

    def post(self, request, pk, **kwargs):
        course = _course_or_404(pk)
        serializer = LessonWriteSerializer(data=request.data, course=course)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            lesson = serializer.save()
            audit.log(request, "academy.lesson_create", lesson, course=course.slug, title=lesson.title)
        return Response(lesson_admin_data(lesson), status=201)


class AdminLessonDetailView(StaffView):
    def get(self, request, pk, **kwargs):
        return Response(lesson_admin_data(get_object_or_404(Lesson, pk=pk)))

    def patch(self, request, pk, **kwargs):
        lesson = get_object_or_404(Lesson.objects.select_related("course"), pk=pk)
        serializer = LessonWriteSerializer(lesson, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            lesson = serializer.save()
            audit.log(request, "academy.lesson_update", lesson, course=lesson.course.slug, title=lesson.title)
        return Response(lesson_admin_data(lesson))

    def delete(self, request, pk, **kwargs):
        lesson = get_object_or_404(Lesson.objects.select_related("course"), pk=pk)
        if lesson.progress.exists() or lesson.comments.exists():
            raise Conflict("Learners have already made progress or commented on this lesson. Unpublish it instead of deleting it.")
        with transaction.atomic():
            audit.log(request, "academy.lesson_delete", lesson, course=lesson.course.slug, title=lesson.title)
            lesson.delete()
        return Response(status=204)


class AdminLessonReorderView(StaffView):
    """POST {"order": [lesson ids]}: the new order, which must list every lesson of the course exactly once."""

    def post(self, request, pk, **kwargs):
        course = _course_or_404(pk)
        ids = request.data.get("order")
        if not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            raise serializers.ValidationError({"order": ["Send the lesson ids in the new order."]})
        with transaction.atomic():
            if not course_service.reorder_lessons(course, ids):
                raise serializers.ValidationError({"order": ["The list must contain every lesson of this course exactly once."]})
            audit.log(request, "academy.lesson_reorder", course, title=course.title, lessons=len(ids))
        return Response([lesson_admin_data(lesson) for lesson in course.lessons.all()])
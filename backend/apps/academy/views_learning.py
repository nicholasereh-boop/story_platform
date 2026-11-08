"""Learner-facing Academy endpoints: the catalog, a course and its outline, lessons, saved progress, lesson comments, My learning.
Access is decided by services/progression.py from stored facts; nothing here trusts the browser."""
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination

from .errors import Conflict
from .models import Course, Enrollment, Lesson, LessonComment, LessonProgress
from .permissions import AcademyEnabled, IsActiveUser
from .serializers_learning import access_data, course_card_data, curriculum_item, lesson_data
from .services import lesson_comments, progression
from .services.progress import record_progress


def _visible_course_or_404(slug, user):
    """A published course; staff may also open drafts (to review them)."""
    course = get_object_or_404(Course.objects.select_related("thumbnail"), slug=slug)
    if course.status != Course.Status.PUBLISHED and not (user.is_authenticated and user.is_staff):
        raise Http404()
    return course


def _visible_lesson_or_404(pk, user):
    lesson = get_object_or_404(Lesson.objects.select_related("course", "course__thumbnail"), pk=pk)
    staff = user.is_authenticated and user.is_staff
    if not staff and (not lesson.is_published or lesson.course.status != Course.Status.PUBLISHED):
        raise Http404()
    return lesson


class PublicView(APIView):
    permission_classes = [AcademyEnabled, AllowAny]
    throttle_scope = "public_read"


class LearnerView(APIView):
    permission_classes = [AcademyEnabled, IsActiveUser]
    parser_classes = [JSONParser]


def _lesson_context(user, lesson):
    states, lessons = progression.compute_states(user, lesson.course)
    state = states.get(lesson.pk)
    if state is None:  # a draft lesson only staff can reach: show it as open to them
        state = {"can_view": bool(user.is_authenticated and user.is_staff), "reason": None, "state": "available", "watch_met": False, "comment_met": False,
                 "requirement_met": False, "requires_comment": False, "percent": 0, "position_seconds": 0, "watched_seconds": 0}
        return state, None, None, lessons
    prev_, next_ = progression.neighbours(lessons, lesson)
    return state, prev_, next_, lessons


class CourseListView(PublicView):
    def get(self, request, **kwargs):
        qs = Course.objects.select_related("thumbnail").filter(status=Course.Status.PUBLISHED).annotate(
            lesson_total=Count("lessons", filter=Q(lessons__is_published=True), distinct=True),
            duration_total=Sum("lessons__duration_seconds", filter=Q(lessons__is_published=True)),
        )
        access = request.query_params.get("access")
        if access in Course.Access.values:
            qs = qs.filter(access_type=access)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(category__icontains=q))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs.order_by("-published_at", "-id"), request, view=self)
        return paginator.get_paginated_response([course_card_data(c) for c in page])


class CourseDetailView(PublicView):
    def get(self, request, slug, **kwargs):
        course = _visible_course_or_404(slug, request.user)
        states, lessons = progression.compute_states(request.user, course)
        signed_in = progression.is_signed_in(request.user)
        summary = progression.course_summary(states, lessons)
        enrolled = signed_in and Enrollment.objects.filter(learner=request.user, course=course, status=Enrollment.Status.ACTIVE).exists()
        from .services import entitlements

        data = course_card_data(course)
        data.update({
            "description": course.description,
            "lessons": [curriculum_item(lesson, states[lesson.pk]) for lesson in lessons],
            "viewer": {
                "authenticated": signed_in, "enrolled": bool(enrolled), "entitled": bool(course.is_paid and entitlements.has_access(request.user, course)),
                **summary,
            },
        })
        return Response(data)


class EnrollView(LearnerView):
    """POST: start a free course (idempotent). Paid courses are never joined this way: they need a verified payment."""

    throttle_scope = "academy_enroll"

    def post(self, request, slug, **kwargs):
        course = _visible_course_or_404(slug, request.user)
        if course.is_paid:
            raise Conflict("This is a paid course. Buy it to start learning.")
        enrollment, created = Enrollment.objects.get_or_create(learner=request.user, course=course, defaults={"source": Enrollment.Source.FREE})
        return Response({"enrolled": True, "created": created}, status=201 if created else 200)


class LessonDetailView(PublicView):
    def get(self, request, pk, **kwargs):
        lesson = _visible_lesson_or_404(pk, request.user)
        state, prev_, next_, lessons = _lesson_context(request.user, lesson)
        states, _ = progression.compute_states(request.user, lesson.course, lessons) if lessons else ({}, None)
        next_state = states.get(next_.pk) if next_ else None
        course = lesson.course
        return Response({
            "lesson": lesson_data(lesson, state),
            "course": {"id": course.pk, "slug": course.slug, "title": course.title, "access_type": course.access_type},
            "access": access_data(state, next_state, next_.pk if next_ else None),
            "progress": {"percent": state["percent"], "position_seconds": state["position_seconds"], "watched_seconds": state["watched_seconds"]},
            "previous_lesson_id": prev_.pk if prev_ else None,
            "next_lesson_id": next_.pk if next_ else None,
        })


class LessonAccessView(PublicView):
    """A cheap re-check of what the learner may do now (used after a comment or a progress save)."""

    def get(self, request, pk, **kwargs):
        lesson = _visible_lesson_or_404(pk, request.user)
        state, _prev, next_, lessons = _lesson_context(request.user, lesson)
        states, _ = progression.compute_states(request.user, lesson.course, lessons) if lessons else ({}, None)
        return Response(access_data(state, states.get(next_.pk) if next_ else None, next_.pk if next_ else None))


def _whole_seconds(data, name, high=86400):
    value = data.get(name, 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or value < 0:
        raise serializers.ValidationError({name: ["Send a number of seconds."]})
    return min(int(value), high)


class LessonProgressView(LearnerView):
    """POST {position_seconds, watched_seconds, duration_seconds}: save where the learner is. Only lessons they may open."""

    throttle_scope = "academy_progress"

    def post(self, request, pk, **kwargs):
        lesson = _visible_lesson_or_404(pk, request.user)
        state, _prev, next_, lessons = _lesson_context(request.user, lesson)
        if not state["can_view"]:
            raise Conflict("This lesson is not open to you yet.")
        position = _whole_seconds(request.data, "position_seconds")
        watched = _whole_seconds(request.data, "watched_seconds")
        duration = _whole_seconds(request.data, "duration_seconds")
        with transaction.atomic():
            progress = record_progress(request.user, lesson, position, watched, duration)
        state, _prev, next_, lessons = _lesson_context(request.user, lesson)
        states, _ = progression.compute_states(request.user, lesson.course, lessons)
        return Response({
            "progress": {"percent": progress.completion_percent, "position_seconds": progress.position_seconds, "watched_seconds": progress.watched_seconds,
                         "completed": progress.completed_at is not None},
            "access": access_data(state, states.get(next_.pk) if next_ else None, next_.pk if next_ else None),
        })


class LessonCommentsView(APIView):
    """GET the comments (anyone who may open the lesson); POST a comment (signed in, lesson open)."""

    permission_classes = [AcademyEnabled]
    parser_classes = [JSONParser]

    def get_permissions(self):
        perms = [AcademyEnabled()]
        if self.request.method == "POST":
            perms.append(IsActiveUser())
        return perms

    def get_throttles(self):
        self.throttle_scope = "academy_comment" if self.request.method == "POST" else "public_read"
        return super().get_throttles()

    def get(self, request, pk, **kwargs):
        lesson = _visible_lesson_or_404(pk, request.user)
        state, *_ = _lesson_context(request.user, lesson)
        if not state["can_view"]:
            return Response({"items": [], "pagination": None, "can_comment": False, "reason": state["reason"]})
        paginator = StandardPagination()
        page = paginator.paginate_queryset(lesson_comments.visible_comments(lesson, request.user), request, view=self)
        response = paginator.get_paginated_response([lesson_comments.comment_data(c, request.user) for c in page])
        return response

    def post(self, request, pk, **kwargs):
        lesson = _visible_lesson_or_404(pk, request.user)
        state, _prev, next_, lessons = _lesson_context(request.user, lesson)
        if not state["can_view"]:
            raise Conflict("This lesson is not open to you yet.")
        comment = lesson_comments.post_comment(request.user, lesson, state, request.data.get("body", ""))
        state, _prev, next_, lessons = _lesson_context(request.user, lesson)
        states, _ = progression.compute_states(request.user, lesson.course, lessons)
        return Response({
            "comment": lesson_comments.comment_data(comment, request.user),
            "access": access_data(state, states.get(next_.pk) if next_ else None, next_.pk if next_ else None),
        }, status=201)


class OwnCommentView(LearnerView):
    """DELETE: remove your own comment. If it was the one that opened the next lesson, that lesson closes again until you comment."""

    def delete(self, request, pk, **kwargs):
        comment = get_object_or_404(LessonComment, pk=pk, user=request.user)
        if comment.status != LessonComment.Status.DELETED:
            comment.status = LessonComment.Status.DELETED
            comment.save(update_fields=["status", "updated_at"])
        return Response(status=204)


class MyLearningView(LearnerView):
    def get(self, request, **kwargs):
        enrollments = (Enrollment.objects.filter(learner=request.user, status=Enrollment.Status.ACTIVE, course__status=Course.Status.PUBLISHED)
                       .select_related("course", "course__thumbnail").order_by("-enrolled_at"))
        items = []
        for enrollment in enrollments:
            course = enrollment.course
            states, lessons = progression.compute_states(request.user, course)
            summary = progression.course_summary(states, lessons)
            last = LessonProgress.objects.filter(learner=request.user, lesson__course=course).order_by("-updated_at").first()
            items.append({**course_card_data(course), **summary, "enrolled_at": enrollment.enrolled_at, "last_activity": last.updated_at if last else None})
        items.sort(key=lambda i: (i["last_activity"] or i["enrolled_at"]), reverse=True)
        return Response({"items": items})
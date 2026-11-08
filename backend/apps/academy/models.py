"""Academy data (extension roadmap: docs/ARCHITECTURE.md). Everything here is new and additive: the Academy never writes to
Story, marketplace or story-comment tables. Access rules live in services/ (progression.py, entitlements.py); the models only
keep the facts and the database-level guarantees (unique rows, valid states)."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Course(models.Model):
    class Level(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Access(models.TextChoices):
        FREE = "free", "Free"
        PAID = "paid", "Paid"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=90, unique=True)
    summary = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)  # plain text, always rendered as text
    level = models.CharField(max_length=14, choices=Level.choices, default=Level.BEGINNER)
    category = models.CharField(max_length=60, blank=True)
    thumbnail = models.ForeignKey("media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")  # the existing image library
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    access_type = models.CharField(max_length=4, choices=Access.choices, default=Access.FREE)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # in `currency`, major units; 0 for free courses
    currency = models.CharField(max_length=3, default="USD")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="academy_courses")
    # The course owner confirms they may use the videos (docs/README.md: "Course owners must confirm they have rights").
    video_rights_confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at", "-id"]
        indexes = [models.Index(fields=["status", "access_type"], name="academy_course_status_idx")]
        constraints = [models.CheckConstraint(condition=Q(access_type="free") | Q(price__gt=0), name="academy_paid_course_has_price")]

    def __str__(self):
        return self.title

    @property
    def is_paid(self):
        return self.access_type == self.Access.PAID


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)  # the order in the course (ties are broken by id)
    youtube_id = models.CharField(max_length=11, blank=True)  # the 11-character id only, never iframe HTML or a URL
    duration_seconds = models.PositiveIntegerField(default=0)  # 0 = not known
    is_intro = models.BooleanField(default=False)  # the optional course introduction: never gated, never gates the next lesson
    is_preview = models.BooleanField(default=False)  # watchable without an account / without buying
    requires_comment_to_unlock_next = models.BooleanField(default=True)
    completion_threshold = models.PositiveSmallIntegerField(default=90)  # percent of the video that counts as "watched"
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        indexes = [models.Index(fields=["course", "position"], name="academy_lesson_order_idx")]
        constraints = [models.CheckConstraint(condition=Q(completion_threshold__gte=10) & Q(completion_threshold__lte=100), name="academy_lesson_threshold_range")]

    def __str__(self):
        return f"{self.course_id}:{self.position} {self.title}"


class Enrollment(models.Model):
    class Source(models.TextChoices):
        FREE = "free", "Free course"
        PURCHASE = "purchase", "Purchase"
        GRANT = "grant", "Complimentary access"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="academy_enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.FREE)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    enrolled_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-enrolled_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["learner", "course"], name="academy_one_enrollment_per_learner_course")]


class LessonProgress(models.Model):
    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="academy_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress")
    watched_seconds = models.PositiveIntegerField(default=0)  # time actually played, summed by the player
    position_seconds = models.PositiveIntegerField(default=0)  # where to resume
    duration_seconds = models.PositiveIntegerField(default=0)  # the video length as last reported
    completion_percent = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)  # when the watch requirement was first met
    completed_via = models.CharField(max_length=10, blank=True)  # "player" or "staff" (the alternative path, always audited)
    last_reported_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "lesson"], name="academy_one_progress_per_learner_lesson")]
        indexes = [models.Index(fields=["learner", "updated_at"], name="academy_progress_learner_idx")]


class LessonComment(models.Model):
    """A comment under a lesson. Academy-owned on purpose: story comments are not touched (docs/IMPORTANT_DECISIONS.md #2)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"  # waiting for staff; visible to its author only
        APPROVED = "approved", "Approved"
        HIDDEN = "hidden", "Hidden"  # hidden by staff
        DELETED = "deleted", "Deleted"

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="academy_comments")
    body = models.TextField()  # plain text
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.APPROVED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["lesson", "status", "created_at"], name="academy_comment_lesson_idx")]


class LessonCommentGate(models.Model):
    """The record that a learner has satisfied the comment requirement of a lesson (one per learner and lesson)."""

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="academy_gates")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="gates")
    comment = models.ForeignKey(LessonComment, null=True, blank=True, on_delete=models.SET_NULL, related_name="gates")
    completed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "lesson"], name="academy_one_gate_per_learner_lesson")]


class CourseOrder(models.Model):
    """One attempt to buy a course. Money records are kept even if the account is later removed (PROTECT)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="academy_orders")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="orders")
    reference = models.CharField(max_length=64, unique=True)  # one reference per order, made by the server
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # what Paystack is asked to CHARGE (charge currency)
    amount_minor = models.BigIntegerField()  # the same in kobo/cents: the exact figure Paystack must confirm
    currency = models.CharField(max_length=3)  # the currency Paystack charges
    list_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # the price shown to the learner
    list_currency = models.CharField(max_length=3, blank=True)
    fx_rate = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PENDING)
    gateway_status = models.CharField(max_length=40, blank=True)
    failure_reason = models.CharField(max_length=60, blank=True)
    paystack_transaction_id = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["learner", "status"], name="academy_order_learner_idx")]


class CourseEntitlement(models.Model):
    """The right to open a paid course. Created ONLY after a verified payment or by an audited staff grant."""

    class Source(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        GRANT = "grant", "Complimentary access"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="academy_entitlements")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="entitlements")
    source = models.CharField(max_length=8, choices=Source.choices)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    order = models.OneToOneField(CourseOrder, null=True, blank=True, on_delete=models.PROTECT, related_name="entitlement")
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)  # null = lifetime access
    note = models.CharField(max_length=200, blank=True)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["learner", "course"], condition=Q(status="active"), name="academy_one_active_entitlement"),
        ]


class AcademyPaymentEvent(models.Model):
    """One processed Paystack webhook delivery for the Academy. The hash of the exact body makes retries harmless."""

    payload_hash = models.CharField(max_length=64, unique=True)
    event = models.CharField(max_length=60)
    reference = models.CharField(max_length=64, blank=True)
    outcome = models.CharField(max_length=40, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
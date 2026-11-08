from django.contrib import admin

from .models import AcademyPaymentEvent, Course, CourseEntitlement, CourseOrder, Enrollment, Lesson, LessonComment, LessonCommentGate, LessonProgress


class ReadOnlyAdmin(admin.ModelAdmin):
    """Money and progress records are evidence: look, never edit."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("position", "title", "youtube_id", "is_intro", "is_preview", "is_published")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "access_type", "price", "currency", "status", "published_at")
    list_filter = ("status", "access_type", "level")
    search_fields = ("title", "slug")
    inlines = [LessonInline]


admin.site.register(Enrollment, ReadOnlyAdmin)
admin.site.register(LessonProgress, ReadOnlyAdmin)
admin.site.register(LessonComment, ReadOnlyAdmin)
admin.site.register(LessonCommentGate, ReadOnlyAdmin)
admin.site.register(CourseOrder, ReadOnlyAdmin)
admin.site.register(CourseEntitlement, ReadOnlyAdmin)
admin.site.register(AcademyPaymentEvent, ReadOnlyAdmin)
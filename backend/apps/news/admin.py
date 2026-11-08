from django.contrib import admin

from .models import NewsArticle, NewsCategory, NewsIngestionRun, NewsRightsRecord, NewsSource, NewsTakedown


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "approval_state", "is_active")
    list_filter = ("approval_state", "source_type", "is_active")
    search_fields = ("name", "slug")


@admin.register(NewsRightsRecord)
class NewsRightsRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "licence", "status", "effective_until")
    list_filter = ("status", "basis")
    search_fields = ("title", "licence")


@admin.register(NewsCategory)
class NewsCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "position", "is_active")


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "status", "published_at")
    list_filter = ("status", "article_type")
    search_fields = ("title", "slug")
    raw_id_fields = ("source", "rights_record", "category")


@admin.register(NewsIngestionRun)
class NewsIngestionRunAdmin(admin.ModelAdmin):
    list_display = ("source", "status", "reason", "created", "started_at")
    list_filter = ("status",)


@admin.register(NewsTakedown)
class NewsTakedownAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "claim", "status", "created_at")
    list_filter = ("status", "claim")

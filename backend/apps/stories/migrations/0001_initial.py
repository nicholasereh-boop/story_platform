import apps.stories.content
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=90, unique=True)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name_plural": "categories", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=70, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Story",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, max_length=220, unique=True)),
                ("excerpt", models.TextField(blank=True, max_length=500)),
                ("content_json", models.JSONField(default=apps.stories.content.empty_doc)),
                ("search_text", models.TextField(blank=True, editable=False)),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("scheduled", "Scheduled"), ("published", "Published"), ("archived", "Archived")],
                        default="draft",
                        max_length=12,
                    ),
                ),
                ("is_featured", models.BooleanField(default=False)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("scheduled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("seo_title", models.CharField(blank=True, max_length=70)),
                ("seo_description", models.CharField(blank=True, max_length=200)),
                ("view_count", models.PositiveIntegerField(default=0)),
                ("like_count", models.PositiveIntegerField(default=0)),
                ("comment_count", models.PositiveIntegerField(default=0)),
                ("categories", models.ManyToManyField(blank=True, related_name="stories", to="stories.category")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
                ("tags", models.ManyToManyField(blank=True, related_name="stories", to="stories.tag")),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "stories",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "published_at"], name="story_status_pub_idx"),
                    models.Index(fields=["created_at"], name="story_created_idx"),
                    models.Index(fields=["updated_at"], name="story_updated_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="StoryRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("revision_number", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=200)),
                ("excerpt", models.TextField(blank=True)),
                ("content_json", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "story",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="stories.story"),
                ),
            ],
            options={
                "ordering": ["-revision_number"],
                "constraints": [models.UniqueConstraint(fields=("story", "revision_number"), name="unique_story_revision_number")],
            },
        ),
    ]

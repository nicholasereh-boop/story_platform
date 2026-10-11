import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("stories", "0002_story_cover_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("value", models.CharField(blank=True, max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("hidden", "Hidden"), ("deleted", "Deleted")],
                        default="approved",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("edited_at", models.DateTimeField(blank=True, null=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="comments.comment"
                    ),
                ),
                (
                    "story",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="stories.story"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="CommentReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "comment",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="comments.comment"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="comment_reports", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["story", "status", "created_at"], name="comment_story_status_idx"),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["status", "created_at"], name="comment_status_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="commentreport",
            constraint=models.UniqueConstraint(fields=("comment", "user"), name="report_unique_comment_user"),
        ),
    ]

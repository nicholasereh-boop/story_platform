import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("stories", "0002_story_cover_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="Visitor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("visitor_key_hash", models.CharField(max_length=64, unique=True)),
                ("first_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_seen_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name="AnalyticsState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=40, unique=True)),
                ("value", models.CharField(blank=True, max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="DailyAnalytics",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True)),
                ("unique_visitors", models.PositiveIntegerField(default=0)),
                ("page_views", models.PositiveIntegerField(default=0)),
                ("story_views", models.PositiveIntegerField(default=0)),
                ("registered_users", models.PositiveIntegerField(default=0)),
                ("likes", models.PositiveIntegerField(default=0)),
                ("comments", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="PeriodAnalytics",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period", models.CharField(choices=[("week", "Week"), ("month", "Month")], max_length=5)),
                ("start_date", models.DateField()),
                ("unique_visitors", models.PositiveIntegerField(default=0)),
                ("page_views", models.PositiveIntegerField(default=0)),
                ("story_views", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="DailyStoryStats",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("views", models.PositiveIntegerField(default=0)),
                ("unique_visitors", models.PositiveIntegerField(default=0)),
                (
                    "story",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="stories.story"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PageViewEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("path", models.CharField(max_length=300)),
                ("session_key_hash", models.CharField(max_length=64)),
                ("referrer_domain", models.CharField(blank=True, max_length=100)),
                (
                    "user_agent_category",
                    models.CharField(
                        choices=[("desktop", "Desktop"), ("mobile", "Mobile"), ("tablet", "Tablet"), ("other", "Other")],
                        default="other",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "story",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="stories.story"
                    ),
                ),
                (
                    "visitor",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="analytics.visitor"),
                ),
            ],
        ),
        migrations.AddIndex(model_name="pageviewevent", index=models.Index(fields=["created_at"], name="pv_created_idx")),
        migrations.AddIndex(
            model_name="pageviewevent", index=models.Index(fields=["story", "created_at"], name="pv_story_created_idx")
        ),
        migrations.AddIndex(
            model_name="pageviewevent", index=models.Index(fields=["visitor", "created_at"], name="pv_visitor_created_idx")
        ),
        migrations.AddConstraint(
            model_name="periodanalytics",
            constraint=models.UniqueConstraint(fields=("period", "start_date"), name="period_unique_start"),
        ),
        migrations.AddConstraint(
            model_name="dailystorystats",
            constraint=models.UniqueConstraint(fields=("date", "story"), name="storystats_unique_date_story"),
        ),
    ]

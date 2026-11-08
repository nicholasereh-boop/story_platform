import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("news", "0002_articles")]

    operations = [
        migrations.CreateModel(
            name="NewsIngestionRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("ok", "Completed"), ("failed", "Failed"), ("skipped", "Skipped")], max_length=8)),
                ("reason", models.CharField(blank=True, max_length=60)),
                ("message", models.CharField(blank=True, max_length=300)),
                ("http_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("fetched", models.PositiveIntegerField(default=0)),
                ("created", models.PositiveIntegerField(default=0)),
                ("duplicates", models.PositiveIntegerField(default=0)),
                ("updated", models.PositiveIntegerField(default=0)),
                ("changed_live", models.PositiveIntegerField(default=0)),
                ("errors", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="runs", to="news.newssource")),
            ],
            options={"ordering": ["-started_at", "-id"]},
        ),
        migrations.AddIndex(model_name="newsingestionrun", index=models.Index(fields=["source", "-started_at"], name="news_run_source_idx")),
    ]

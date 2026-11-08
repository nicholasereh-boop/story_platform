import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("news", "0003_ingestion_runs")]

    operations = [
        migrations.CreateModel(
            name="NewsTakedown",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_ref", models.CharField(blank=True, max_length=300)),
                ("contact_name", models.CharField(max_length=120)),
                ("contact_email", models.EmailField(max_length=254)),
                ("claim", models.CharField(default="copyright", max_length=20)),
                ("message", models.TextField(max_length=4000)),
                ("status", models.CharField(choices=[("open", "Open"), ("on_hold", "Article on hold"), ("upheld", "Upheld (article withdrawn)"), ("dismissed", "Dismissed")], default="open", max_length=10)),
                ("resolution_note", models.CharField(blank=True, max_length=300)),
                ("handled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("article", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="takedowns", to="news.newsarticle")),
                ("handled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(model_name="newstakedown", index=models.Index(fields=["status", "-created_at"], name="news_takedown_status_idx")),
    ]

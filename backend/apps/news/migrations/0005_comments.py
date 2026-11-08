import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("news", "0004_takedowns")]

    operations = [
        migrations.CreateModel(
            name="NewsComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("hidden", "Hidden"), ("deleted", "Deleted")], default="approved", max_length=9)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("article", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="news.newsarticle")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="news_comments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(model_name="newscomment", index=models.Index(fields=["article", "status", "created_at"], name="news_comment_article_idx")),
    ]

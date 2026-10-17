from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("reactions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="like",
            name="like_unique_user_story",
        ),
        migrations.AlterField(
            model_name="like",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="likes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="like",
            name="session_key",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=40,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="like",
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=False),
                fields=("user", "story"),
                name="like_unique_user_story",
            ),
        ),
        migrations.AddConstraint(
            model_name="like",
            constraint=models.UniqueConstraint(
                condition=models.Q(session_key__isnull=False),
                fields=("session_key", "story"),
                name="like_unique_session_story",
            ),
        ),
    ]
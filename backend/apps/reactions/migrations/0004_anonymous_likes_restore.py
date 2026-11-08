import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Anonymous (session) likes again: user becomes optional, session_key is added, uniqueness is per reader kind."""

    dependencies = [
        ("reactions", "0003_remove_like_like_unique_user_story_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="like", name="like_unique_user_story"),
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
            field=models.CharField(blank=True, db_index=True, max_length=40, null=True),
        ),
        migrations.AddConstraint(
            model_name="like",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", False)), fields=("user", "story"), name="like_unique_user_story"
            ),
        ),
        migrations.AddConstraint(
            model_name="like",
            constraint=models.UniqueConstraint(
                condition=models.Q(("session_key__isnull", False)),
                fields=("session_key", "story"),
                name="like_unique_session_story",
            ),
        ),
        migrations.AddConstraint(
            model_name="like",
            constraint=models.CheckConstraint(
                condition=models.Q(("user__isnull", False), ("session_key__isnull", False), _connector="OR"),
                name="like_has_reader",
            ),
        ),
    ]

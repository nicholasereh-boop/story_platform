import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Anonymous visitors can comment: user becomes optional; session_key + guest_name identify and name them."""

    dependencies = [
        ("comments", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="comment",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="comments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="comment",
            name="session_key",
            field=models.CharField(blank=True, db_index=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name="comment",
            name="guest_name",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
        migrations.AddConstraint(
            model_name="comment",
            constraint=models.CheckConstraint(
                condition=models.Q(("user__isnull", False), ("session_key__isnull", False), _connector="OR"),
                name="comment_has_author",
            ),
        ),
    ]

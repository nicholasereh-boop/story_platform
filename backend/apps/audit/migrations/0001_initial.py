import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_label", models.CharField(blank=True, max_length=120)),
                ("action", models.CharField(max_length=60)),
                ("object_type", models.CharField(blank=True, max_length=40)),
                ("object_id", models.CharField(blank=True, max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["action", "created_at"], name="audit_action_created_idx"),
                    models.Index(fields=["object_type", "object_id"], name="audit_object_idx"),
                    models.Index(fields=["actor", "created_at"], name="audit_actor_created_idx"),
                ],
            },
        ),
    ]

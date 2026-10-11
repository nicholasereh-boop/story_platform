import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MFADevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("secret_encrypted", models.CharField(max_length=300)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_step", models.BigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, related_name="mfa_device", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MFARecoveryCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code_hash", models.CharField(max_length=64)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="mfa_recovery_codes", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="mfarecoverycode",
            constraint=models.UniqueConstraint(fields=("user", "code_hash"), name="mfa_recovery_unique_user_hash"),
        ),
        migrations.CreateModel(
            name="UserSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(max_length=40, unique=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("device", models.CharField(blank=True, max_length=80)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="tracked_sessions", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={"ordering": ["-last_seen_at", "-id"]},
        ),
    ]

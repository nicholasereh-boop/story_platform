import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="NewsSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("source_type", models.CharField(choices=[("original", "ResourceBoard original reporting"), ("licensed", "Licensed (written permission or agreement)"), ("open_licensed", "Open licence (for example Creative Commons)"), ("public_domain", "Verified public domain"), ("metadata_only", "Headlines and links only")], default="licensed", max_length=14)),
                ("website_url", models.URLField(blank=True, max_length=300)),
                ("terms_url", models.URLField(blank=True, max_length=300)),
                ("adapter", models.CharField(blank=True, choices=[("", "Manual entry only"), ("rss", "RSS or Atom feed")], default="", max_length=8)),
                ("feed_url", models.URLField(blank=True, max_length=500)),
                ("is_active", models.BooleanField(default=False)),
                ("approval_state", models.CharField(choices=[("pending", "Waiting for approval"), ("approved", "Approved"), ("suspended", "Suspended"), ("rejected", "Rejected")], default="pending", max_length=10)),
                ("allows_full_text", models.BooleanField(default=False)),
                ("allows_commercial_use", models.BooleanField(default=False)),
                ("attribution_template", models.CharField(blank=True, max_length=400)),
                ("evidence_ref", models.CharField(blank=True, max_length=300)),
                ("renewal_contact", models.CharField(blank=True, max_length=200)),
                ("poll_interval_minutes", models.PositiveIntegerField(default=60)),
                ("max_items_per_poll", models.PositiveIntegerField(default=20)),
                ("daily_request_quota", models.PositiveIntegerField(default=24)),
                ("notes", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="NewsRightsRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("licence", models.CharField(max_length=80)),
                ("licence_version", models.CharField(blank=True, max_length=20)),
                ("licence_url", models.URLField(blank=True, max_length=300)),
                ("basis", models.CharField(choices=[("original", "ResourceBoard's own work"), ("written_permission", "Written permission"), ("syndication_agreement", "Syndication agreement"), ("open_licence", "Open licence"), ("public_domain", "Public domain")], max_length=24)),
                ("allows_full_text", models.BooleanField(default=False)),
                ("allows_commercial_use", models.BooleanField(default=False)),
                ("allows_modification", models.BooleanField(default=False)),
                ("requires_attribution", models.BooleanField(default=True)),
                ("requires_counter", models.BooleanField(default=False)),
                ("allows_caching", models.BooleanField(default=True)),
                ("allows_archive", models.BooleanField(default=True)),
                ("retention_days", models.PositiveIntegerField(blank=True, null=True)),
                ("restrictions", models.TextField(blank=True)),
                ("effective_from", models.DateTimeField(default=django.utils.timezone.now)),
                ("effective_until", models.DateTimeField(blank=True, null=True)),
                ("evidence_url", models.URLField(blank=True, max_length=500)),
                ("evidence_note", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("approved", "Approved"), ("revoked", "Revoked"), ("expired", "Expired")], default="draft", max_length=8)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_reason", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="rights_records", to="news.newssource")),
            ],
            options={"ordering": ["-effective_from", "-id"]},
        ),
        migrations.AddIndex(model_name="newssource", index=models.Index(fields=["approval_state", "is_active"], name="news_source_state_idx")),
        migrations.AddIndex(model_name="newsrightsrecord", index=models.Index(fields=["source", "status"], name="news_rights_source_idx")),
    ]

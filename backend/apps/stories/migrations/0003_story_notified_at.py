from django.db import migrations, models
from django.utils import timezone


def mark_existing_as_notified(apps, schema_editor):
    """Stories that are already out must not be emailed to everybody the day this update is installed."""
    Story = apps.get_model("stories", "Story")
    Story.objects.exclude(status="draft").update(notified_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ("stories", "0002_story_cover_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(mark_existing_as_notified, migrations.RunPython.noop),
    ]

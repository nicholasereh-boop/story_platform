import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("media", "0001_initial"),
        ("stories", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="cover_image",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="media.mediaasset"
            ),
        ),
    ]

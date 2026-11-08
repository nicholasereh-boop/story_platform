
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("reactions", "0005_merge_20261023_1435"),
    ]

    operations = [
        # Remove constraints belonging to the obsolete session_key design.
        migrations.RemoveConstraint(
            model_name="like",
            name="like_unique_session_story",
        ),
        migrations.RemoveConstraint(
            model_name="like",
            name="like_has_reader",
        ),

        # Remove the old field; visitor_id is the current anonymous identifier.
        migrations.RemoveField(
            model_name="like",
            name="session_key",
        ),
    ]

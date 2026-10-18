from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_mfa_and_sessions"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="email_new_stories",
            field=models.BooleanField(default=True),
        ),
    ]

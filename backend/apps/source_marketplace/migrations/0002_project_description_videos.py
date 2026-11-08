from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('source_marketplace', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='sourceproject',
            name='backend_video_id',
            field=models.CharField(blank=True, max_length=11),
        ),
        migrations.AddField(
            model_name='sourceproject',
            name='frontend_video_id',
            field=models.CharField(blank=True, max_length=11),
        ),
    ]
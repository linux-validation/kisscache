from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("kiss_cache", "0017_downloaded_speed")]

    operations = [
        migrations.AddField(
            model_name="resource",
            name="extra_headers",
            field=models.JSONField(default=dict),
            preserve_default=False,
        )
    ]

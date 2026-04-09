from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("kiss_cache", "0016_resource_url_4096")]

    operations = [
        migrations.AddField(
            model_name="resource",
            name="downloaded_speed",
            field=models.FloatField(default=0),
            preserve_default=False,
        )
    ]

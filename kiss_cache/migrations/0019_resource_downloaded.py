from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("kiss_cache", "0018_extra_headers")]

    operations = [
        migrations.AddField(
            model_name="resource",
            name="downloaded",
            field=models.BigIntegerField(default=0),
        )
    ]

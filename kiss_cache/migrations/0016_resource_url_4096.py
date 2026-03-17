from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kiss_cache", "0015_mirror"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resource",
            name="url",
            field=models.URLField(max_length=4096, unique=True),
        ),
    ]

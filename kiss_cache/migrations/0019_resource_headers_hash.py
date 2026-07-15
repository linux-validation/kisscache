from django.db import migrations, models


def drop_header_resources(apps, schema_editor):
    """
    Evict resources that were fetched with headers.

    Before this migration a url was unique and its cached file lived at a path
    derived from the url alone. A resource is now unique by url *and* headers,
    and a fetched-with-headers resource stores its file at a header-dependent
    path. The existing files are at the old path, so the safest upgrade is to
    drop these rows and let them be re-fetched to their new location on next
    use. Resources fetched without headers are untouched: their path and file
    are unchanged.

    The post_delete signal is not connected to the historical model, so the old
    files are not unlinked here. They are harmless: an unauthenticated fetch of
    the same url reuses (and overwrites) that exact path, otherwise the file is
    simply never referenced again.
    """
    Resource = apps.get_model("kiss_cache", "Resource")
    pks = [
        res.pk
        for res in Resource.objects.only("pk", "extra_headers").iterator()
        if res.extra_headers
    ]
    Resource.objects.filter(pk__in=pks).delete()


class Migration(migrations.Migration):
    dependencies = [("kiss_cache", "0018_extra_headers")]

    operations = [
        migrations.AddField(
            model_name="resource",
            name="headers_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.RunPython(drop_header_resources, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="resource",
            name="url",
            field=models.URLField(max_length=4096),
        ),
        migrations.AlterUniqueTogether(
            name="resource",
            unique_together={("url", "headers_hash")},
        ),
        migrations.RemoveField(model_name="resource", name="extra_headers"),
    ]

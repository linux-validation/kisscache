# -*- coding: utf-8 -*-
# vim: set ts=4
#
# Copyright 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: MIT

import json

from django.http import FileResponse, HttpResponse, JsonResponse
from django.http.response import StreamingHttpResponse
from django.urls import reverse
from django.utils import timezone

from kiss_cache.__about__ import __version__
from kiss_cache.models import Resource, Statistic


def test_index(client):
    ret = client.get(reverse("home"))
    assert len(ret.templates) == 2
    assert ret.templates[0].name == "kiss_cache/index.html"
    assert ret.templates[1].name == "kiss_cache/base.html"
    assert ret.context["api_url"] == "http://testserver/api/v1/fetch"
    assert ret.context["delete_url"] == "http://testserver/api/v1/delete"
    assert ret.context["version"] == __version__


def test_help(client):
    ret = client.get(reverse("help"))
    assert len(ret.templates) == 2
    assert ret.templates[0].name == "kiss_cache/help.html"
    assert ret.templates[1].name == "kiss_cache/base.html"
    assert ret.context["ALLOWED_NETWORKS"] == []
    assert ret.context["user_ip"] == "127.0.0.1"
    assert ret.context["user_ip_allowed"] == True
    assert ret.context["api_url"] == "http://testserver/api/v1/fetch"
    assert ret.context["delete_url"] == "http://testserver/api/v1/delete"


def test_statistics(client, db, settings):
    # Empty page
    ret = client.get(reverse("statistics"))
    assert len(ret.templates) == 2
    assert ret.templates[0].name == "kiss_cache/statistics.html"
    assert ret.templates[1].name == "kiss_cache/base.html"
    assert ret.context["total_size"] == 0
    assert ret.context["quota"] == settings.RESOURCE_QUOTA
    assert ret.context["progress"] == 0
    assert ret.context["progress_status"] == "success"
    assert ret.context["scheduled_count"] == 0
    assert ret.context["downloading_count"] == 0
    assert ret.context["successes_count"] == 0
    assert ret.context["failures_count"] == 0
    assert ret.context["statistics_download"] == 0
    assert ret.context["statistics_upload"] == 0
    assert ret.context["statistics_requests"] == 0

    # Create some resources
    MEGA = 1024 * 1024
    Resource.objects.create(url="http://example.com/1", state=Resource.STATE_SCHEDULED)
    Resource.objects.create(
        url="http://example.com/2",
        state=Resource.STATE_DOWNLOADING,
        content_length=111 * MEGA,
    )
    Resource.objects.create(
        url="http://example.com/3",
        state=Resource.STATE_FINISHED,
        status_code=200,
        content_length=222 * MEGA,
    )
    Resource.objects.create(
        url="http://example.com/4",
        state=Resource.STATE_FINISHED,
        status_code=504,
        content_length=333 * MEGA,
    )
    Statistic.objects.filter(stat=Statistic.STAT_DOWNLOAD).update(value=666 * MEGA)
    Statistic.objects.filter(stat=Statistic.STAT_UPLOAD).update(value=2 * 666 * MEGA)
    ret = client.get(reverse("statistics"))
    assert len(ret.templates) == 2
    assert ret.templates[0].name == "kiss_cache/statistics.html"
    assert ret.templates[1].name == "kiss_cache/base.html"
    assert ret.context["total_size"] == 666 * MEGA
    assert ret.context["quota"] == settings.RESOURCE_QUOTA
    assert ret.context["progress"] == 13
    assert ret.context["progress_status"] == "success"
    assert ret.context["scheduled_count"] == 1
    assert ret.context["downloading_count"] == 1
    assert ret.context["successes_count"] == 1
    assert ret.context["failures_count"] == 1
    assert ret.context["statistics_download"] == 666 * MEGA
    assert ret.context["statistics_upload"] == 2 * 666 * MEGA
    assert ret.context["statistics_requests"] == 0


def test_resources(client, db):
    # Empty page
    ret = client.get(reverse("resources.successes"))
    assert len(ret.templates) == 2
    assert ret.templates[0].name == "kiss_cache/resources.html"
    assert ret.templates[1].name == "kiss_cache/base.html"
    assert len(ret.context["resources"].object_list) == 0
    assert ret.context["resources"].number == 1
    assert ret.context["state"] == "successes"
    assert ret.context["url_name"] == "resources.successes"
    assert ret.context["scheduled_count"] == 0
    assert ret.context["downloading_count"] == 0
    assert ret.context["successes_count"] == 0
    assert ret.context["failures_count"] == 0

    # Create some resources
    MEGA = 1024 * 1024
    Resource.objects.create(url="http://example.com/1", state=Resource.STATE_SCHEDULED)
    Resource.objects.create(
        url="http://example.com/2",
        state=Resource.STATE_DOWNLOADING,
        content_length=111 * MEGA,
    )
    Resource.objects.create(
        url="http://example.com/3",
        state=Resource.STATE_FINISHED,
        status_code=200,
        content_length=222 * MEGA,
    )
    Resource.objects.create(
        url="http://example.com/4",
        state=Resource.STATE_FINISHED,
        status_code=504,
        content_length=333 * MEGA,
    )

    Statistic.objects.filter(stat=Statistic.STAT_DOWNLOAD).update(value=666 * MEGA)
    Statistic.objects.filter(stat=Statistic.STAT_UPLOAD).update(value=2 * 666 * MEGA)

    # Test each pages
    ret = client.get(reverse("resources.scheduled"))
    assert len(ret.templates) == 2
    assert ret.templates[0].name == "kiss_cache/resources.html"
    assert ret.templates[1].name == "kiss_cache/base.html"
    assert len(ret.context["resources"].object_list) == 1
    assert ret.context["resources"].object_list[0].url == "http://example.com/1"
    assert ret.context["resources"].number == 1
    assert ret.context["state"] == "scheduled"
    assert ret.context["url_name"] == "resources.scheduled"
    assert ret.context["scheduled_count"] == 1
    assert ret.context["downloading_count"] == 1
    assert ret.context["successes_count"] == 1
    assert ret.context["failures_count"] == 1

    ret = client.get(reverse("resources.downloading"))
    assert len(ret.templates) == 2
    assert ret.templates[0].name == "kiss_cache/resources.html"
    assert ret.templates[1].name == "kiss_cache/base.html"
    assert len(ret.context["resources"].object_list) == 1
    assert ret.context["resources"].object_list[0].url == "http://example.com/2"
    assert ret.context["resources"].number == 1
    assert ret.context["state"] == "downloading"
    assert ret.context["url_name"] == "resources.downloading"
    assert ret.context["scheduled_count"] == 1
    assert ret.context["downloading_count"] == 1
    assert ret.context["successes_count"] == 1
    assert ret.context["failures_count"] == 1

    ret = client.get(reverse("resources.successes"))
    assert len(ret.templates) == 2
    assert ret.templates[0].name == "kiss_cache/resources.html"
    assert ret.templates[1].name == "kiss_cache/base.html"
    assert len(ret.context["resources"].object_list) == 1
    assert ret.context["resources"].object_list[0].url == "http://example.com/3"
    assert ret.context["resources"].number == 1
    assert ret.context["state"] == "successes"
    assert ret.context["url_name"] == "resources.successes"
    assert ret.context["scheduled_count"] == 1
    assert ret.context["downloading_count"] == 1
    assert ret.context["successes_count"] == 1
    assert ret.context["failures_count"] == 1

    ret = client.get(reverse("resources.failures"))
    assert len(ret.templates) == 2
    assert ret.templates[0].name == "kiss_cache/resources.html"
    assert ret.templates[1].name == "kiss_cache/base.html"
    assert len(ret.context["resources"].object_list) == 1
    assert ret.context["resources"].object_list[0].url == "http://example.com/4"
    assert ret.context["resources"].number == 1
    assert ret.context["state"] == "failures"
    assert ret.context["url_name"] == "resources.failures"
    assert ret.context["scheduled_count"] == 1
    assert ret.context["downloading_count"] == 1
    assert ret.context["successes_count"] == 1
    assert ret.context["failures_count"] == 1

    # Test errors
    ret = client.get(reverse("resources.failures") + "?order=-usag")
    assert ret.status_code == 400
    ret = client.get(reverse("resources.failures") + "10/")
    assert ret.status_code == 404


def test_api_health(client, mocker, settings, tmpdir):
    settings.SHUTDOWN_PATH = str(tmpdir / "shutdown")
    ret = client.get(reverse("api.health"))

    (tmpdir / "shutdown").write_text("", encoding="utf-8")
    ret = client.get(reverse("api.health"))
    assert ret.status_code == 503


def test_api_fetch(client, db, mocker, settings, tmpdir):
    URL = "https://example.com"

    def mocked_fetch(url, extra_headers):
        assert url == URL
        Resource.objects.filter(url=URL).update(
            state=Resource.STATE_FINISHED,
            status_code=200,
            content_length=12,
            content_type="text/html; charset=UTF-8",
        )
        path = Resource.objects.get(url=URL).path
        assert (
            path == "10/0680ad546ce6a577f42f52df33b4cfdca756859e664b8d7de329b150d09ce9"
        )
        (tmpdir / "10").mkdir()
        (
            tmpdir / "10/0680ad546ce6a577f42f52df33b4cfdca756859e664b8d7de329b150d09ce9"
        ).write_text("Hello world!", encoding="utf-8")

    settings.DOWNLOAD_PATH = str(tmpdir)

    fetch = mocker.patch("kiss_cache.tasks.fetch.delay", mocked_fetch)

    # Download a first time with nginx backend
    ret = client.get(f"{reverse('api.fetch')}?url={URL}&ttl=42d")
    assert isinstance(ret, HttpResponse)
    assert ret["X-Accel-Redirect"] == str(
        "/internal/10/0680ad546ce6a577f42f52df33b4cfdca756859e664b8d7de329b150d09ce9"
    )

    assert ret.status_code == 200
    assert ret["content-type"] == "text/html; charset=UTF-8"
    assert ret["content-length"] == "0"

    # Download a second time with apache2 backend
    settings.XSENDFILE_BACKEND = "apache2"
    ret = client.get(f"{reverse('api.fetch')}?url={URL}&ttl=42d")
    assert isinstance(ret, HttpResponse)
    assert ret["X-Sendfile"] == str(
        tmpdir / "10/0680ad546ce6a577f42f52df33b4cfdca756859e664b8d7de329b150d09ce9"
    )
    assert ret.status_code == 200
    assert ret["content-type"] == "text/html; charset=UTF-8"
    assert ret["content-length"] == "0"

    # Download a third time and set a shorter ttl
    now = timezone.now()
    mocker.patch("django.utils.timezone.now", lambda: now)
    ret = client.get(f"{reverse('api.fetch')}?url={URL}&ttl=4d")
    assert isinstance(ret, HttpResponse)
    assert ret["X-Sendfile"] == str(
        tmpdir / "10/0680ad546ce6a577f42f52df33b4cfdca756859e664b8d7de329b150d09ce9"
    )
    assert ret.status_code == 200
    assert ret["content-type"] == "text/html; charset=UTF-8"
    assert ret["content-length"] == "0"
    assert Resource.objects.get(url=URL).ttl == 345_600

    # Download a forth time: set the Content-Disposition
    # Do not use xsendfile anymore
    settings.USE_XSENDFILE = False
    ret = client.get(
        f"{reverse('api.fetch_by_filename', kwargs={'filename': 'kernel'})}?url={URL}"
    )
    assert isinstance(ret, FileResponse)
    assert ret.status_code == 200
    assert ret["content-type"] == "text/html; charset=UTF-8"
    assert ret["content-length"] == "12"
    assert next(ret.streaming_content) == b"Hello world!"
    assert ret["content-disposition"] == "attachment; filename=kernel"

    # Download a fifth time with status_code = 404
    Resource.objects.filter(url=URL).update(status_code=404)
    ret = client.get(f"{reverse('api.fetch')}?url={URL}")
    assert ret.status_code == 404


def test_api_fetch_streaming(client, db, mocker, settings, tmpdir):
    URL = "https://example.com"

    def mocked_fetch(url, extra_headers):
        assert url == URL
        Resource.objects.filter(url=URL).update(
            state=Resource.STATE_DOWNLOADING,
            status_code=200,
            content_length=12,
            content_type="text/html; charset=UTF-8",
        )
        path = Resource.objects.get(url=URL).path
        assert (
            path == "10/0680ad546ce6a577f42f52df33b4cfdca756859e664b8d7de329b150d09ce9"
        )
        (tmpdir / "10").mkdir()
        (
            tmpdir / "10/0680ad546ce6a577f42f52df33b4cfdca756859e664b8d7de329b150d09ce9"
        ).write_text("Hello world!", encoding="utf-8")

    settings.DOWNLOAD_PATH = str(tmpdir)

    fetch = mocker.patch("kiss_cache.tasks.fetch.delay", mocked_fetch)
    ret = client.get(
        f"{reverse('api.fetch_by_filename', kwargs={'filename': 'ramdisk.tgz'})}?url={URL}&ttl=42d"
    )
    assert isinstance(ret, StreamingHttpResponse)
    assert ret.status_code == 200
    assert ret["content-type"] == "text/html; charset=UTF-8"
    assert ret["content-length"] == "12"
    assert ret["content-disposition"] == "attachment; filename=ramdisk.tgz"
    assert next(ret.streaming_content) == b"Hello world!"


def test_api_fetch_headers(client, db, mocker, settings, tmpdir):
    """The same url fetched with different headers is cached separately"""
    import pathlib

    URL = "https://example.com"
    settings.DOWNLOAD_PATH = str(tmpdir)
    settings.USE_XSENDFILE = False

    fetched = []

    def mocked_fetch(url, extra_headers):
        # The worker resolves the resource by url and headers, exactly as the
        # real task does, and writes distinct content per credential.
        fetched.append(extra_headers)
        res = Resource.objects.get(
            url=url, headers_hash=Resource.hash_headers(extra_headers)
        )
        body = extra_headers.get("Authorization", "anonymous").encode("utf-8")
        Resource.objects.filter(pk=res.pk).update(
            state=Resource.STATE_FINISHED, status_code=200, content_length=len(body)
        )
        res.refresh_from_db()
        path = pathlib.Path(str(tmpdir)) / res.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    mocker.patch("kiss_cache.tasks.fetch.delay", mocked_fetch)

    # First client, with its own token
    ret = client.get(f"{reverse('api.fetch')}?url={URL}", HTTP_AUTHORIZATION="one")
    assert ret.status_code == 200
    assert b"".join(ret.streaming_content) == b"one"

    # Second client, different token: a separate resource, downloaded again
    ret = client.get(f"{reverse('api.fetch')}?url={URL}", HTTP_AUTHORIZATION="two")
    assert ret.status_code == 200
    assert b"".join(ret.streaming_content) == b"two"

    # Two resources for the same url, two downloads, two distinct files
    assert Resource.objects.filter(url=URL).count() == 2
    assert len(fetched) == 2
    paths = {res.path for res in Resource.objects.filter(url=URL)}
    assert len(paths) == 2

    # First token again: served from cache, no new resource, no new download
    ret = client.get(f"{reverse('api.fetch')}?url={URL}", HTTP_AUTHORIZATION="one")
    assert ret.status_code == 200
    assert b"".join(ret.streaming_content) == b"one"
    assert Resource.objects.filter(url=URL).count() == 2
    assert len(fetched) == 2


def test_api_delete(client, db, settings, tmpdir):
    import pathlib

    URL = "https://example.com"
    settings.DOWNLOAD_PATH = str(tmpdir)

    res = Resource.objects.create(
        url=URL,
        state=Resource.STATE_FINISHED,
        status_code=200,
        content_length=5,
    )
    (tmpdir / "10").mkdir()
    fpath = tmpdir / "10/0680ad546ce6a577f42f52df33b4cfdca756859e664b8d7de329b150d09ce9"
    fpath.write_text("hello", encoding="utf-8")
    assert fpath.exists()

    # A second copy of the same url fetched with headers
    auth = Resource.objects.create(
        url=URL,
        headers_hash=Resource.hash_headers({"Authorization": "token"}),
        state=Resource.STATE_FINISHED,
        status_code=200,
        content_length=5,
    )
    auth_path = pathlib.Path(str(tmpdir)) / auth.path
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text("hello", encoding="utf-8")
    assert auth_path.exists()

    # Missing url
    ret = client.get(reverse("api.delete"))
    assert ret.status_code == 400

    # Unknown resource
    ret = client.get(f"{reverse('api.delete')}?url=https://example.com/missing")
    assert ret.status_code == 404

    # Delete by url removes every cached copy and their files
    ret = client.get(f"{reverse('api.delete')}?url={URL}")
    assert ret.status_code == 200
    assert Resource.objects.filter(url=URL).count() == 0
    assert not fpath.exists()
    assert not auth_path.exists()


def test_api_fetch_errors(client, db, mocker):
    URL = "https://example.com"

    #  missing url
    ret = client.get(reverse("api.fetch"))
    assert ret.status_code == 400

    # Invalid ttl format
    ret = client.get(f"{reverse('api.fetch')}?url={URL}&ttl=1k")
    assert ret.status_code == 400

    # Over quota
    mocker.patch("kiss_cache.models.Resource.is_over_quota", lambda: True)
    ret = client.get(f"{reverse('api.fetch')}?url={URL}")
    assert ret.status_code == 507


def test_api_status(client, db):
    ret = client.get(reverse("api.status"))
    assert ret.status_code == 200
    assert isinstance(ret, JsonResponse)
    data = json.loads(ret.content)
    assert data["disk_usage"] == 0
    assert data["disk_usage_percent"] == 0
    assert data["disk_quota"] == 5_368_709_120
    assert data["instance"] == "http://testserver/"
    assert data["resources_scheduled"] == 0
    assert data["resources_downloading"] == 0
    assert data["resources_successes"] == 0
    assert data["resources_failures"] == 0
    assert data["resources_usage"] == 0
    assert data["statistics_successes"] == 0
    assert data["statistics_failures"] == 0
    assert data["statistics_download"] == 0
    assert data["statistics_upload"] == 0
    assert data["statistics_requests"] == 0
    assert data["version"] == __version__
    assert "timestamp" in data

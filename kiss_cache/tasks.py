# -*- coding: utf-8 -*-
# vim: set ts=4
#
# Copyright 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: MIT

import contextlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import logging
import os
import pathlib
import requests
import time

from celery import shared_task
from celery.utils.log import get_task_logger

from django.conf import settings
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from kiss_cache.__about__ import __version__
from kiss_cache.models import Resource, Statistic
from kiss_cache.utils import requests_retry


# Setup the loggers
logging.getLogger("requests").setLevel(logging.WARNING)
LOG = get_task_logger(__name__)


def _base_headers(extra_headers):
    # Only accept plain content (not gzipped) so that the Content-Length is
    # known and range requests address the real bytes.
    return {
        "Accept-Encoding": "",
        "User-Agent": f"KissCache/{__version__}",
        **extra_headers,
    }


def _total_size(req):
    """
    Total size of the resource from the first (probe) response, or None.

    A 206 answer carries the total in its Content-Range header ("bytes 0-N/M"),
    otherwise we fall back to the Content-Length of a plain 200 answer.
    """
    if req.status_code == 206:
        content_range = req.headers.get("Content-Range", "")
        with contextlib.suppress(ValueError, IndexError):
            return int(content_range.rsplit("/", 1)[1])
    with contextlib.suppress(TypeError, ValueError):
        return int(req.headers.get("Content-Length"))
    return None


def _connection_count(content_length, accept_ranges):
    """Number of parallel connections to use for the download."""
    if not accept_ranges or not content_length:
        return 1
    count = min(
        settings.DOWNLOAD_CONCURRENCY,
        content_length // settings.DOWNLOAD_MIN_SEGMENT_SIZE,
    )
    return max(1, count)


def _segments(content_length, count):
    """
    Split the resource into byte ranges, one per connection.

    A single connection downloads the whole resource (end is None), which also
    covers the case where the content length is unknown.
    """
    if count <= 1:
        return [(0, None)]
    size = content_length // count
    segments = []
    start = 0
    for i in range(count):
        end = content_length - 1 if i == count - 1 else start + size - 1
        segments.append((start, end))
        start = end + 1
    return segments


def _watermark(segments, progress):
    """Number of contiguous bytes available from the start of the file."""
    watermark = 0
    for i, (start, end) in enumerate(segments):
        watermark = start + progress[i]
        if end is None:
            break
        if progress[i] < end - start + 1:
            break
    return watermark


def _consume_segment(url, req, segment, fd, progress, idx, results):
    """Write a segment's response body at its offset in the file."""
    start, end = segment
    # The probe connection requests an open-ended range, so it may stream more
    # than its segment: keep only the bytes this segment is responsible for.
    limit = None if end is None else end - start + 1
    try:
        offset = start
        written = 0
        try:
            for data in req.iter_content(
                chunk_size=settings.DOWNLOAD_CHUNK_SIZE, decode_unicode=False
            ):
                if limit is not None and written + len(data) > limit:
                    data = data[: limit - written]
                os.pwrite(fd, data, offset)
                offset += len(data)
                written += len(data)
                progress[idx] = written
                if limit is not None and written >= limit:
                    break
        finally:
            req.close()
        results[idx] = 0
    except requests.RequestException as exc:
        LOG.error("Unable to fetch '%s'", url)
        LOG.exception(exc)
        results[idx] = 504
    except Exception as exc:  # noqa: B902 - never let a worker die silently
        LOG.error("Unable to fetch '%s'", url)
        LOG.exception(exc)
        results[idx] = 504


def _fetch_segment(url, headers, segment, fd, progress, idx, results):
    """Open a ranged connection for a segment and download it."""
    start, end = segment
    seg_headers = dict(headers)
    seg_headers["Range"] = f"bytes={start}-{end}"
    try:
        req = requests_retry().get(
            url, stream=True, headers=seg_headers, timeout=settings.DOWNLOAD_TIMEOUT
        )
    except requests.RequestException as exc:
        LOG.error("Unable to connect to '%s'", url)
        LOG.exception(exc)
        results[idx] = 502
        return
    if req.status_code != 206:
        LOG.error("'%s' returned %d", url, req.status_code)
        req.close()
        results[idx] = req.status_code
        return
    _consume_segment(url, req, segment, fd, progress, idx, results)


@shared_task(ignore_result=True)
def fetch(url, extra_headers={}):
    LOG.info("Fetching '%s'", url)
    # Grab the object from the database
    try:
        res = Resource.objects.get(url=url)
    except Resource.DoesNotExist:
        LOG.error("Resource db object does not exist for '%s'", url)
        return

    # Create the directory
    try:
        base = pathlib.Path(settings.DOWNLOAD_PATH)
        (base / res.path).parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    except OSError as exc:
        LOG.error("Unable to create the directory '%s'", str((base / res.path)))
        LOG.exception(exc)
        Resource.objects.filter(pk=res.pk).update(
            state=Resource.STATE_FINISHED, status_code=500
        )
        Statistic.failures(1)
        return

    try:
        _download(res, extra_headers)
    except Exception as exc:  # noqa: B902 - mark the resource as failed and move on
        LOG.error("Unable to fetch '%s'", url)
        LOG.exception(exc)
        Resource.objects.filter(pk=res.pk).update(
            state=Resource.STATE_FINISHED, status_code=504
        )
        Statistic.failures(1)


def _download(res, extra_headers):
    url = res.url
    base_headers = _base_headers(extra_headers)
    path = str(pathlib.Path(settings.DOWNLOAD_PATH) / res.path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        # Open the first connection with an open-ended range request. This both
        # downloads the first segment and probes whether the server supports
        # range requests (206) and what the total size is. Servers that do not
        # support ranges answer 200 with the full body, which is then downloaded
        # over this single connection.
        probe_headers = dict(base_headers)
        if settings.DOWNLOAD_CONCURRENCY > 1:
            probe_headers["Range"] = "bytes=0-"
        try:
            req0 = requests_retry().get(
                url,
                stream=True,
                headers=probe_headers,
                timeout=settings.DOWNLOAD_TIMEOUT,
            )
        except requests.RequestException as exc:
            LOG.error("Unable to connect to '%s'", url)
            LOG.exception(exc)
            Resource.objects.filter(pk=res.pk).update(
                state=Resource.STATE_FINISHED, status_code=502
            )
            Statistic.failures(1)
            return

        if req0.status_code not in (200, 206):
            LOG.error("'%s' returned %d", url, req0.status_code)
            req0.close()
            Resource.objects.filter(pk=res.pk).update(
                state=Resource.STATE_FINISHED, status_code=req0.status_code
            )
            Statistic.failures(1)
            return

        accept_ranges = req0.status_code == 206
        content_type = req0.headers.get("Content-Type", "")
        total = _total_size(req0)
        count = _connection_count(total, accept_ranges)
        segments = _segments(total, count)
        progress = [0] * len(segments)
        results = [None] * len(segments)

        # Pre-allocate the file so segments can be written at their offsets.
        if count > 1 and total:
            os.ftruncate(fd, total)

        # Inform the callers that the download started so they can stream it.
        Resource.objects.filter(pk=res.pk).update(
            content_length=total,
            content_type=content_type or "",
            status_code=200,
            state=Resource.STATE_DOWNLOADING,
            downloaded=0,
            extra_headers=extra_headers,
        )

        start = time.time()
        with ThreadPoolExecutor(max_workers=len(segments)) as pool:
            # The first segment is served by the probe connection; the remaining
            # segments open their own ranged connections.
            pool.submit(
                _consume_segment, url, req0, segments[0], fd, progress, 0, results
            )
            for i in range(1, len(segments)):
                pool.submit(
                    _fetch_segment,
                    url,
                    base_headers,
                    segments[i],
                    fd,
                    progress,
                    i,
                    results,
                )
            # Persist the contiguous watermark while the segments download so
            # that streaming clients can follow the progress. Only the main
            # thread touches the database; the workers only do network/file I/O.
            last = 0
            while any(result is None for result in results):
                watermark = _watermark(segments, progress)
                if watermark != last:
                    Resource.objects.filter(pk=res.pk).update(downloaded=watermark)
                    last = watermark
                time.sleep(settings.DOWNLOAD_WATERMARK_INTERVAL)

        size = sum(progress)
        watermark = _watermark(segments, progress)
        elapsed = time.time() - start
        speed = 0.0
        with contextlib.suppress(ZeroDivisionError):
            speed = round(size / (1024 * 1024 * elapsed), 2)

        # A non-zero result is the HTTP status code (or 50x) of a failed segment.
        failure = next((result for result in results if result), 0)
        if failure:
            # Drop the not-yet-downloaded holes so a streaming client errors out
            # instead of receiving zeroes.
            os.ftruncate(fd, watermark)
            Resource.objects.filter(pk=res.pk).update(
                state=Resource.STATE_FINISHED,
                status_code=failure,
                downloaded=watermark,
                downloaded_speed=speed,
            )
            Statistic.failures(1)
            return

        if total and total != size:
            LOG.error(
                "The total size (%d) is not equal to the Content-Length (%d)",
                size,
                total,
            )
            os.ftruncate(fd, watermark)
            Resource.objects.filter(pk=res.pk).update(
                state=Resource.STATE_FINISHED,
                status_code=504,
                downloaded=watermark,
                downloaded_speed=speed,
            )
            Statistic.download(size)
            Statistic.failures(1)
            return

        LOG.info(
            "%dMB downloaded in %0.2fs (%0.2fMB/s)",
            size / (1024 * 1024),
            round(elapsed, 2),
            speed,
        )
        Statistic.download(size)
        Statistic.successes(1)
        Resource.objects.filter(pk=res.pk).update(
            state=Resource.STATE_FINISHED,
            content_length=size,
            content_type=content_type or "",
            downloaded=size,
            downloaded_speed=speed,
        )
    finally:
        os.close(fd)


@shared_task(ignore_result=True)
def expire():
    LOG.info("Removing failed resources")
    query = Resource.objects.filter(state=Resource.STATE_FINISHED)
    for res in query.exclude(status_code=200):
        LOG.info("* '%s'", res.url)
        res.delete()
    LOG.info("done")

    LOG.info("Expiring resources")
    for res in Resource.objects.filter(state=Resource.STATE_FINISHED):
        if res.created_at + timedelta(seconds=res.ttl) < timezone.now():
            LOG.info("* '%s'", res.url)
            res.delete()
    LOG.info("done")

    LOG.info("Checking quota usage")
    limit = settings.RESOURCE_QUOTA * settings.RESOURCE_QUOTA_AUTO_CLEAN / 100
    if Resource.total_size() > limit:
        LOG.info(
            "* Cleaning by last usage (%s > %s)",
            filesizeformat(Resource.total_size()),
            filesizeformat(limit),
        )
        last_usage_limit = timezone.now() - timedelta(
            seconds=settings.RESOURCE_QUOTA_AUTO_CLEAN_DELAY
        )
        while Resource.total_size() > limit:
            try:
                q = Resource.objects.filter(state=Resource.STATE_FINISHED)
                q = q.filter(last_usage__lt=last_usage_limit)
                res = q.order_by("last_usage")[0]
                LOG.info("  - %s: '%s'", filesizeformat(res.content_length), res.url)
                res.delete()
            except IndexError:
                LOG.info("* No more resources to clean")
                break
    LOG.info("* Usage: %s", filesizeformat(Resource.total_size()))
    LOG.info("done")

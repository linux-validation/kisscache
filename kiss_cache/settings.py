# -*- coding: utf-8 -*-
# vim: set ts=4
#
# Copyright 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: MIT

# fail after 10 minutes
DOWNLOAD_TIMEOUT = 10 * 60
# See https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html
DOWNLOAD_RETRY = 15
# A backoff factor to apply between attempts after the second try (most errors
# are resolved immediately by a second try without a delay). urllib3 will sleep
# for:
#    {backoff factor} * (2 ** ({number of total retries} - 1))
# seconds. If the backoff_factor is 0.1, then sleep() will sleep for [0.0s,
# 0.2s, 0.4s, …] between retries.
DOWNLOAD_BACKOFF_FACTOR = 0.1

# base directory
DOWNLOAD_PATH = "/var/cache/kiss-cache"

# Download 1kB by 1kB
DOWNLOAD_CHUNK_SIZE = 1024

# Number of parallel connections used to download a resource. KissCache always
# downloads in parallel and automatically falls back to a single connection when
# the remote server does not support range requests, the content length is
# unknown, or the resource is too small. Set to 1 to disable parallel downloads.
DOWNLOAD_CONCURRENCY = 30
# A resource is split into at most content_length // DOWNLOAD_MIN_SEGMENT_SIZE
# connections, so resources smaller than this are downloaded over a single
# connection.
DOWNLOAD_MIN_SEGMENT_SIZE = 16 * 1024 * 1024
# Interval (in seconds) at which the contiguous download watermark is persisted
# so that streaming clients can follow the download progress.
DOWNLOAD_WATERMARK_INTERVAL = 1

# By default, keep the resources for 10 days
DEFAULT_TTL = "10d"

# When this file exists, a call to /api/v1/health/ will return 503
# Allow to implement graceful shutdown and interact with load balancers
SHUTDOWN_PATH = "/var/lib/kiss-cache/shutdown"

# Celery specific configuration
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_CONCURRENCY = 10
CELERY_WORKER_SEND_TASK_EVENTS = True

# Setup the scheduler
CELERY_BEAT_SCHEDULE = {
    "expire-every-minute": {"task": "kiss_cache.tasks.expire", "schedule": 60}
}
CELERY_BEAT_MAX_LOOP_INTERVAL = 30

# List of networks that can fetch resources
# By default the instance is fully open
ALLOWED_NETWORKS = []

# Comma-separated list of HTTP Headers that KissCache will pass onto a fetch
PASS_HEADERS = "Authorization,Authentication,Authorisation"

# Default quota of 5G
RESOURCE_QUOTA = 5 * 1024 * 1024 * 1024
# Automatically remove old resources when the quota usage is above this value
# (percent)
RESOURCE_QUOTA_AUTO_CLEAN = 75
# Only consider resources that where not used for N seconds
RESOURCE_QUOTA_AUTO_CLEAN_DELAY = 3600

# Use the apache2 xsendfile module
USE_XSENDFILE = True
# xsendfile backend ("nginx" or "apache2")
XSENDFILE_BACKEND = "nginx"

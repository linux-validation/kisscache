# vim: set ts=4
#
# Copyright 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: MIT

from django.apps import AppConfig


class KissCacheConfig(AppConfig):
    name = "kiss_cache"

    def ready(self):
        import kiss_cache.signals  # noqa: F401 (side-effect import to register signals)

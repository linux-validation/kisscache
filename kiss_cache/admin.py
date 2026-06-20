# vim: set ts=4
#
# Copyright 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: MIT

from django.contrib import admin
from django.template.defaultfilters import filesizeformat

from kiss_cache.models import Resource, Statistic, Mirror


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("url", "path", "state", "status_code", "ttl", "usage")
    list_filter = ("state", "status_code")
    ordering = ["url"]
    readonly_fields = ("created_at", "path", "url")


@admin.register(Statistic)
class StatisticAdmin(admin.ModelAdmin):
    list_display = ("stat_display", "value", "humanized")
    ordering = ["stat"]

    @admin.display(description="Statistic")
    def stat_display(self, obj):
        return obj.get_stat_display()

    def humanized(self, obj):
        if obj.stat in [Statistic.STAT_DOWNLOAD, Statistic.STAT_UPLOAD]:
            return filesizeformat(obj.value)


@admin.register(Mirror)
class MirrorAdmin(admin.ModelAdmin):
    list_display = ("url_pattern", "mirrors")
    search_fields = ("url_pattern",)

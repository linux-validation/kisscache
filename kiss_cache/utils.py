# -*- coding: utf-8 -*-
# vim: set ts=4
#
# Copyright 2019 Linaro Limited
# Copyright 2024 NXP
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
# Author: Andy Sabathier <andy.sabathier@nxp.com>
#
# SPDX-License-Identifier: MIT

from functools import wraps
import ipaddress
import requests
import contextlib
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseForbidden
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from django.http import (
    HttpResponse,
)

from kiss_cache.models import Mirror


def get_user_ip(request):
    if "HTTP_X_FORWARDED_FOR" in request.META:
        return request.META["HTTP_X_FORWARDED_FOR"].split(",")[0]
    if "REMOTE_ADDR" in request.META:
        return request.META["REMOTE_ADDR"]
    raise Exception("Unable to get the user ip")


def is_client_allowed(request):
    # If ALLOWED_NETWORKS is empty: accept every clients
    if not settings.ALLOWED_NETWORKS:
        return True
    # Filter the client
    user_ip = get_user_ip(request)
    client_ip = ipaddress.ip_address(user_ip)
    for rule in settings.ALLOWED_NETWORKS:
        if client_ip in ipaddress.ip_network(rule):
            return True
    # Nothing matching: access is denied
    return False


def get_authorized_mirror_url(url, auth_header=None):
    """
    Determines the best available URL (including mirrors) that is both accessible and authorized.

    Args:
        url (str): The original URL to fetch.
        auth_header (str, optional): Authorization header for authentication.

    Returns:
        tuple: A tuple containing:
            - test_url (str or None): The first valid URL or None if no valid URL is found.
            - response (HttpResponse): The corresponding HTTP response.
            - authorized (bool): Indicates whether the request is authorized (True or False).
    """
    # Initialize headers for the request
    headers = {"User-Agent": "KissCache"}
    if auth_header:
        headers["Authorization"] = auth_header
    authorized = True
    urls_to_check = []

    # Fetch all mirrors from the database and check if they match the original URL
    mirrors_queryset = Mirror.objects.all()
    for mirror in mirrors_queryset:
        if mirror.match_url(url):  # Check if the mirror applies to the given URL
            for mirror_url in mirror.get_preferred_mirrors():
                parsed_url = urlparse(url)
                modified_url = f"{parsed_url.scheme}://{mirror_url}{parsed_url.path}"
                urls_to_check.append(modified_url)

    # If no mirrors were found, add the original URL as a fallback
    if not urls_to_check:
        urls_to_check.append(url)

    # Iterate through all URLs to check their validity and authorization status
    for test_url in urls_to_check:
        with contextlib.suppress(requests.RequestException):
            response = requests.head(
                test_url, headers=headers, timeout=settings.DOWNLOAD_TIMEOUT
            )
            if response.status_code == 200:
                return test_url, response, authorized
            elif response.status_code == 401:
                authorized = False
                # Create an unauthorized HTTP response with the appropriate header
                response_obj = HttpResponse("Unauthorized", status=401)
                response_obj["WWW-Authenticate"] = 'Basic realm="KissCache"'
                return test_url, response_obj, authorized

    # If no valid URL is found, return a 404 response
    return url, HttpResponse("No valid URL found", status=404), authorized


def check_client_ip(func):
    @wraps(func)
    def inner(request, *args, **kwargs):
        if is_client_allowed(request):
            return func(request, *args, **kwargs)
        # Nothing matching: access is denied
        return HttpResponseForbidden()

    return inner


def requests_retry():
    session = requests.Session()
    retries = settings.DOWNLOAD_RETRY
    backoff_factor = settings.DOWNLOAD_BACKOFF_FACTOR
    status_forcelist = [
        # See https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
        408,  # Request Timeout
        413,  # Payload Too Large
        425,  # Too Early
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
        507,  # Insufficient Storage
        # Unofficial codes
        420,  # Enhance Your Calm
        430,  # Request Header Fields Too Large
        509,  # Bandwidth Limit Exceeded
        529,  # Site is overloaded
        598,  # (Informal convention) Network read timeout error
    ]
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        status=retries,
        status_forcelist=status_forcelist,
        backoff_factor=backoff_factor,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

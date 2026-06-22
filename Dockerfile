ARG PYTHON_VERSION="3.13"
ARG UV_VERSION="0.11"
ARG VERSION="dev"

FROM ghcr.io/astral-sh/uv:${UV_VERSION}-python${PYTHON_VERSION}-trixie-slim

LABEL maintainer="Rémi Duraffort <remi.duraffort@linaro.org>"

ENV DEBIAN_FRONTEND=noninteractive
ENV PKG_DEPS="\
  adduser \
  libjs-jquery \
  nginx \
  postgresql-client \
"
ENV PATH="/app/.venv/bin:$PATH" \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_COMPILE_BYTECODE=1

# Install dependencies
RUN apt-get update -q=2 && \
    apt-get install -q=2 --yes --no-install-recommends ${PKG_DEPS} && \
    # Drop default nginx site
    rm -f /etc/nginx/sites-enabled/default && \
    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pyproject.toml and uv.lock for dependency layer caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project

# Create Django project skeleton
RUN addgroup --system --gid 200 kiss-cache && \
    adduser --system --uid 200 --gid 200 kiss-cache && \
    django-admin startproject website /app

# Copy project source files
COPY kiss_cache/ /app/kiss_cache/
COPY share/init.py /app/website/__init__.py
COPY share/celery.py /app/website/celery.py
COPY share/settings.py /app/website/custom_settings.py
COPY share/urls.py /app/website/urls.py

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-editable

# Apply build-time patches
RUN echo "INSTALLED_APPS.append(\"kiss_cache\")" >> /app/website/settings.py && \
    echo "from kiss_cache.settings import *" >> /app/website/settings.py && \
    echo "from website.custom_settings import *" >> /app/website/settings.py && \
    echo "__version__ = \"$VERSION\"" >> /app/kiss_cache/__about__.py && \
    uv run python manage.py collectstatic --noinput && \
    mkdir -p /var/cache/kiss-cache /var/lib/kiss-cache && \
    chown -R kiss-cache:kiss-cache /var/cache/kiss-cache /var/lib/kiss-cache

# Run as non-root user
USER kiss-cache

COPY share/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

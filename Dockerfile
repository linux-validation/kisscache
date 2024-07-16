FROM debian:bookworm-slim

LABEL maintainer="Rémi Duraffort <remi.duraffort@linaro.org>"

ENV DEBIAN_FRONTEND=noninteractive
ENV PKG_DEPS="\
  gunicorn \
  libjs-jquery \
  nginx \
  postgresql-client \
  python3-celery \
  python3-django \
  python3-django-auth-ldap \
  python3-pip \
  python3-psycopg2 \
  python3-redis \
  python3-requests \
  python3-sentry-sdk \
  python3-whitenoise \
  python3-yaml \
"

# Install dependencies
RUN echo 'deb http://deb.debian.org/debian bookworm-backports main' > /etc/apt/sources.list.d/backports.list && \
    mkdir -p /usr/share/man/man1 /usr/share/man/man7 && \
    apt update -q=2 && \
    apt full-upgrade -q=2 --yes && \
    apt install -q=2 --yes --no-install-recommends ${PKG_DEPS} && \
    # Drop default nginx site
    rm /etc/nginx/sites-enabled/default && \
    # Cleanup
    apt-get clean && \
    find /usr/lib/python3/dist-packages/ -name '__pycache__' -type d -exec rm -r "{}" + && \
    rm -rf /var/lib/apt/lists/*

# Create the django project
WORKDIR /app/
RUN addgroup --system --gid 200 kiss-cache && \
    adduser --system --uid 200 --gid 200 kiss-cache && \
    mkdir -p /var/cache/kiss-cache /var/lib/kiss-cache && \
    chown -R kiss-cache /var/cache/kiss-cache /var/lib/kiss-cache && \
    chmod 775 /app && \
    django-admin startproject website /app

# Add entrypoint
COPY share/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# Add sources
COPY kiss_cache/ /app/kiss_cache/
COPY share/init.py /app/website/__init__.py
COPY share/celery.py /app/website/celery.py
COPY share/settings.py /app/website/custom_settings.py
COPY share/urls.py /app/website/urls.py

# Setup kiss_cache application
ARG VERSION="dev"
RUN echo "INSTALLED_APPS.append(\"kiss_cache\")" >> /app/website/settings.py && \
    echo "from kiss_cache.settings import *" >> /app/website/settings.py && \
    echo "from website.custom_settings import *" >> /app/website/settings.py && \
    echo "__version__ = \"$VERSION\"" >> /app/kiss_cache/__about__.py && \
    # Migrate and collect static files
    python3 manage.py collectstatic --noinput

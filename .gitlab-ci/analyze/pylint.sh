#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  uv sync --frozen --no-install-project --group dev
else
  set -x
  uv run ruff check kiss_cache tests/
fi

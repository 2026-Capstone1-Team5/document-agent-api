#!/bin/sh
set -eu

uv run alembic upgrade head
exec uv run uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"

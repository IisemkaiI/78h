#!/bin/sh
# Amvera entrypoint: migrate the managed PostgreSQL database, then serve
# the API and the compiled SPA from a single uvicorn process.
set -eu

: "${PORT:=8000}"
: "${CERTIFICATES_STORAGE_DIR:=/data/certificates}"
export PORT
export CERTIFICATES_STORAGE_DIR

# Amvera mounts persistent storage at /data. The image runs as root only long
# enough to make the mount writable for the unprivileged application user.
mkdir -p "$CERTIFICATES_STORAGE_DIR" 2>/dev/null || true
chown -R app:app "$CERTIFICATES_STORAGE_DIR" 2>/dev/null || true

echo "[vector] applying database migrations"
gosu app alembic upgrade head

echo "[vector] starting API on 0.0.0.0:${PORT}"
exec gosu app uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --proxy-headers \
    --forwarded-allow-ips='*'

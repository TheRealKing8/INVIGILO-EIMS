#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh — Invigilo backend container entrypoint
# =============================================================================
#
# Order of operations (matters; do not re-order without testing):
#
#   1. Wait for Postgres. The compose healthcheck gates ``depends_on`` so
#      this should already be true, but a cold start where the healthcheck
#      hasn't run yet still needs us to wait. Belt + braces.
#   2. Run ``manage.py migrate --noinput``. Idempotent; safe on every boot.
#   3. ``exec gunicorn``. The ``exec`` is deliberate — it replaces the
#      shell with gunicorn so the gunicorn process is PID 1 and the
#      container's SIGTERM reaches it directly. Without ``exec``, the
#      container takes 10s to die on ``docker compose down``.
#
# Phase 0 SSE constraint: ``-w 1``. Phase 20's apps/realtime/pubsub.py is
# an in-process module-level singleton — a Notification saved in worker A
# would never wake a subscriber in worker B. The single-worker gunicorn
# (matching the Render free-tier's single dyno) is the only correct config
# until we swap to Redis pubsub. See the TODO in pubsub.py.
# =============================================================================
set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-invigilo}"
POSTGRES_DB="${POSTGRES_DB:-invigilo}"

echo "[entrypoint] waiting for postgres at ${POSTGRES_HOST}:${POSTGRES_PORT} ..."
# 30s budget; pg_isready exits 0 the moment the server accepts connections.
# The compose healthcheck already covers this for normal starts, but a
# restart loop that races the healthcheck benefits from the explicit wait.
for _ in $(seq 1 30); do
  if pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" > /dev/null 2>&1; then
    echo "[entrypoint] postgres is ready"
    break
  fi
  sleep 1
done
if ! pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" > /dev/null 2>&1; then
  echo "[entrypoint] postgres not reachable after 30s; bailing" >&2
  exit 1
fi

echo "[entrypoint] running database migrations ..."
python manage.py migrate --noinput

echo "[entrypoint] starting gunicorn (-w 1) on 0.0.0.0:8000 ..."
exec gunicorn invigilo.wsgi:application \
  --workers 1 \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -

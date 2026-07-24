#!/usr/bin/env bash
# =============================================================================
# lock-pg-hba.sh — flip pg_hba.conf to scram-sha-256 and restart postgres
# =============================================================================
#
# Phase 0 bash port of restore-pg-hba.ps1 for the Docker container.
# Replaces the postgres container's pg_hba.conf with a scram-sha-256-only
# config and restarts the container so the new file takes effect.
#
# Mechanism: the official postgres image's pg_hba.conf lives at
# ``/var/lib/postgresql/data/pg_hba.conf`` inside the container. We
# ``docker cp`` the new file in, then ``docker compose restart`` the
# postgres service. A timestamped backup of the old file is preserved
# inside the container for the audit trail.
#
# This is the only place Phase 0 touches the named volume directly. All
# other ops go through the application layer.
#
# Usage:  ./lock-pg-hba.sh
#         POSTGRES_CONTAINER=invigilo-postgres ./lock-pg-hba.sh
# =============================================================================
set -euo pipefail

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-invigilo-postgres}"
HBA_PATH="/var/lib/postgresql/data/pg_hba.conf"

# Sanity: the container must be running.
if ! docker ps --format '{{.Names}}' | grep -qx "${POSTGRES_CONTAINER}"; then
  echo "[hba] container ${POSTGRES_CONTAINER} is not running; bailing" >&2
  exit 1
fi

# New pg_hba.conf content. scram-sha-256 for both local + host TCP.
# ``trust`` lines are removed entirely; anything that needed them
# (e.g. the rotate-pg-passwords.sh call) must run BEFORE this script.
NEW_HBA='# Phase 0 — scram-sha-256 only. trust lines are gone.
# local connections (psql inside the container)
local   all             all                                     scram-sha-256
# TCP from any host (docker network + the host operator)
host    all             all             0.0.0.0/0               scram-sha-256
host    all             all             ::/0                    scram-sha-256
'

# Back up the existing file inside the container, then replace.
TS="$(date +%Y%m%d-%H%M%S)"
echo "[hba] backing up ${HBA_PATH} to ${HBA_PATH}.bak.trust-${TS} ..."
docker exec "${POSTGRES_CONTAINER}" \
  sh -c "cp '${HBA_PATH}' '${HBA_PATH}.bak.trust-${TS}'"

echo "[hba] writing new scram-sha-256 config ..."
# Pipe the new content through docker exec with a here-doc-ish pattern
# so we don't have to write a temp file on the host.
docker exec -i "${POSTGRES_CONTAINER}" \
  sh -c "cat > '${HBA_PATH}'" <<EOF
${NEW_HBA}
EOF

# Restart so the new file is re-read.
echo "[hba] restarting ${POSTGRES_CONTAINER} ..."
docker compose restart postgres

# Give it a moment, then confirm it came back in scram-sha-256 mode
# (i.e. trust lines are gone).
sleep 3
if docker exec "${POSTGRES_CONTAINER}" grep -q '^[^#]*trust' "${HBA_PATH}"; then
  echo "[hba] trust lines still present; bailing" >&2
  exit 1
fi
echo "[hba] lockdown complete (trust lines removed)"

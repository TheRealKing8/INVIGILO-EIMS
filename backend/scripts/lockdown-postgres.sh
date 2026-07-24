#!/usr/bin/env bash
# =============================================================================
# lockdown-postgres.sh — orchestrator for the trust → scram-sha-256 flow
# =============================================================================
#
# Phase 0 bash port of lockdown-postgres.ps1. The Docker variant of
# the SECURITY.md runbook. Runs in this order, pausing between steps
# so the operator can read the output:
#
#   1. rotate-pg-passwords.sh   — first, while trust mode is still on
#   2. lock-pg-hba.sh           — flips pg_hba.conf to scram-sha-256
#   3. restart-backend.sh       — restarts the gunicorn so it picks up
#                                  the new .env
#   4. verify-dashboard.sh      — smoke test the API
#
# Designed to be run from the host (not inside the container) so the
# ``docker compose restart`` in step 3 hits the right service. All
# four sub-scripts can also be run independently.
#
# Usage:  ./lockdown-postgres.sh
#         SKIP_PAUSE=1 ./lockdown-postgres.sh   # CI / unattended
# =============================================================================
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PAUSE="${SKIP_PAUSE:-}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"

pause() {
  if [ -z "${PAUSE}" ]; then
    echo
    read -rp "Press Enter to continue (or Ctrl-C to abort) ..."
  fi
}

echo "================================================================="
echo "  Phase 0 — Postgres lockdown (trust -> scram-sha-256)"
echo "================================================================="
echo
echo "Step 1/4 — rotate passwords"
echo "-----------------------------------------------------------------"
"${SCRIPTS_DIR}/rotate-pg-passwords.sh"
pause

echo
echo "Step 2/4 — lock pg_hba.conf to scram-sha-256"
echo "-----------------------------------------------------------------"
"${SCRIPTS_DIR}/lock-pg-hba.sh"
pause

echo
echo "Step 3/4 — restart ${BACKEND_SERVICE} service"
echo "-----------------------------------------------------------------"
docker compose restart "${BACKEND_SERVICE}"
# Give gunicorn a moment to come back up before step 4's curl.
sleep 3
pause

echo
echo "Step 4/4 — verify dashboard"
echo "-----------------------------------------------------------------"
"${SCRIPTS_DIR}/verify-dashboard.sh"

echo
echo "================================================================="
echo "  Lockdown complete."
echo "================================================================="

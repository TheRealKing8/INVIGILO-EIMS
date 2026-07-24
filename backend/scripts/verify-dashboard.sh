#!/usr/bin/env bash
# =============================================================================
# verify-dashboard.sh — confirm the API still answers after a lockdown
# =============================================================================
#
# Phase 0 bash port of verify-dashboard.ps1. Hits each of the 5 module
# list endpoints with a fresh login + bearer token; asserts 200. Exits
# non-zero on the first failure.
#
# Usage:  ./verify-dashboard.sh
#         EMAIL=admininvigilo@gmail.com PASSWORD=secret ./verify-dashboard.sh
#
# Env (defaults match the seed in apps/accounts/migrations/0002_seed_rbac.py):
#   BASE_URL   — default http://localhost:8000
#   EMAIL      — default admininvigilo@gmail.com
#   PASSWORD   — default AdminInvigilo!2026 (the dev box default; do not
#                use in production — the .env should override this)
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
EMAIL="${EMAIL:-admininvigilo@gmail.com}"
PASSWORD="${PASSWORD:-AdminInvigilo!2026}"

echo "[verify] logging in as ${EMAIL} ..."
TOKEN="$(curl -fs -X POST "${BASE_URL}/api/v1/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" \
  | python -c "import json,sys; print(json.load(sys.stdin)['access'])")"

if [ -z "${TOKEN}" ]; then
  echo "[verify] login returned no access token; bailing" >&2
  exit 1
fi
echo "[verify] got token (${#TOKEN} chars)"

# Five module list endpoints + a health probe. The module endpoints
# require the admin's perms; the health endpoint is public.
ENDPOINTS=(
  "/api/v1/health/"
  "/api/v1/exams/"
  "/api/v1/exams/sessions/"
  "/api/v1/allocations/"
  "/api/v1/incidents/"
  "/api/v1/invigilators/"
  "/api/v1/notifications/"
)

FAIL=0
for ep in "${ENDPOINTS[@]}"; do
  HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}${ep}")"
  if [ "${HTTP_CODE}" = "200" ]; then
    echo "[verify] OK   ${HTTP_CODE}  ${ep}"
  else
    echo "[verify] FAIL ${HTTP_CODE}  ${ep}" >&2
    FAIL=1
  fi
done

if [ "${FAIL}" -ne 0 ]; then
  echo "[verify] one or more endpoints failed" >&2
  exit 1
fi
echo "[verify] all endpoints healthy"

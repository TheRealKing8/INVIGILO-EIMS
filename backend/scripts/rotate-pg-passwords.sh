#!/usr/bin/env bash
# =============================================================================
# rotate-pg-passwords.sh — rotate postgres + invigilo role passwords
# =============================================================================
#
# Phase 0 bash port of rotate-pg-passwords.ps1. Must run while the
# Postgres server is still in trust mode (so the postgres superuser can
# connect without a password); this is the case during a fresh
# docker compose up on a volume that has never been locked down.
#
# Two roles are rotated:
#   * ``postgres`` — the superuser. The new password goes to
#     ``POSTGRES_SUPERUSER_PASSWORD`` in backend/.env (or rewrites an
#     existing ``POSTGRES_PASSWORD`` line if the legacy name is in use).
#   * ``invigilo`` — the application role. Goes to ``POSTGRES_PASSWORD``.
#
# Both passwords are 28 random base64 chars (≈168 bits of entropy).
# The script backs up backend/.env to backend/.env.bak.<ts> before
# editing and prints the new passwords once (so the operator can
# record them in 1Password / Bitwarden / wherever). They are NOT
# echoed after the script exits.
#
# Usage:  ./rotate-pg-passwords.sh
#         PGHOST=127.0.0.1 PGPORT=5432 ./rotate-pg-passwords.sh
#         (the defaults target the postgres container)
# =============================================================================
set -euo pipefail

PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-invigilo}"
ENV_FILE="${ENV_FILE:-$(dirname "$0")/../.env}"

# Sanity: env file must exist and be writable.
if [ ! -f "${ENV_FILE}" ]; then
  echo "[rotate] env file not found: ${ENV_FILE}" >&2
  exit 1
fi

# Two fresh random passwords. openssl rand -base64 24 gives 32 chars
# (base64 includes padding); strip the padding + trim to 28 for the
# same length as the PowerShell script used.
gen_pw() { openssl rand -base64 24 | tr -d '=+/' | cut -c1-28; }
PG_PW="$(gen_pw)"
APP_PW="$(gen_pw)"

# Back up .env before touching it.
TS="$(date +%Y%m%d-%H%M%S)"
cp "${ENV_FILE}" "${ENV_FILE}.bak.${TS}"
echo "[rotate] backed up env to ${ENV_FILE}.bak.${TS}"

# Connect as the postgres superuser (trust mode = no password needed) and
# ALTER both users. The ``invigilo`` role may not exist yet on a fresh
# volume; we CREATE it if missing, ALTER it otherwise.
echo "[rotate] rotating passwords in postgres ..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'invigilo') THEN
    CREATE ROLE invigilo LOGIN PASSWORD '${APP_PW}';
    GRANT ALL PRIVILEGES ON DATABASE invigilo TO invigilo;
  ELSE
    ALTER ROLE invigilo WITH PASSWORD '${APP_PW}';
  END IF;
END
\$\$;
ALTER ROLE postgres WITH PASSWORD '${PG_PW}';
SQL

# Patch .env in place. We replace the password values, preserving
# everything else. Uses python for the sed-equivalent because the
# passwords can contain characters that confuse sed/grep.
echo "[rotate] writing new passwords to ${ENV_FILE} ..."
python <<PY
import os, re
path = "${ENV_FILE}"
with open(path) as f:
    text = f.read()

# POSTGRES_PASSWORD: rewrite (the application's role).
new = re.sub(
    r'^(POSTGRES_PASSWORD=).*$',
    r'\\g<1>${APP_PW}',
    text,
    flags=re.M,
)

# POSTGRES_SUPERUSER_PASSWORD: insert or rewrite. The PowerShell
# variant used this name; the .env.example uses POSTGRES_PASSWORD for
# the superuser too on Docker. Handle both: write both, preferring
# the legacy name so existing scripts keep working.
if re.search(r'^POSTGRES_SUPERUSER_PASSWORD=', new, flags=re.M):
    new = re.sub(
        r'^(POSTGRES_SUPERUSER_PASSWORD=).*$',
        r'\\g<1>${PG_PW}',
        new,
        flags=re.M,
    )
else:
    new = re.sub(
        r'^(POSTGRES_PASSWORD=.*)$',
        r'\\g<1>\nPOSTGRES_SUPERUSER_PASSWORD=${PG_PW}',
        new,
        count=1,
        flags=re.M,
    )

# DATABASE_URL: rebuild with the new app password.
new = re.sub(
    r'^(DATABASE_URL=postgres://)([^:]+):([^@]+)@([^:/]+)(:\d+)?(/[^\s]*)?$',
    r'\\g<1>\\g<2>:${APP_PW}@\\g<4>\\g<5>\\g<6>',
    new,
    flags=re.M,
)

with open(path, "w") as f:
    f.write(new)
PY

echo "[rotate] done. new passwords (save these now; they will not be echoed again):"
echo "  POSTGRES_SUPERUSER_PASSWORD=${PG_PW}"
echo "  POSTGRES_PASSWORD=${APP_PW}"

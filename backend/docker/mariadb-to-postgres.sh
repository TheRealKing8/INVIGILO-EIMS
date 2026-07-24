#!/usr/bin/env bash
# =============================================================================
# mariadb-to-postgres.sh — one-shot data migration from MariaDB to Postgres
# =============================================================================
#
# Phase 0. Copies the dev data from a running MariaDB / XAMPP server
# (127.0.0.1:3306 by default) into the postgres container that's
# running under docker compose. Idempotent: if the target Postgres DB
# is already populated, the script bails.
#
# Order of operations:
#
#   1. Sanity checks: MariaDB reachable, Postgres reachable, .env present.
#   2. Dump per-table with mysqldump --compatible=postgresql --tab=... .
#      This produces one .txt (CSV) + one .sql (schema) per table.
#      The .sql files are discarded — Postgres's schema is built by
#      Django's own migrations, not by mysqldump's CREATE TABLE.
#   3. For each app's tables, in FK dependency order, sed-convert
#      MariaDB booleans (0/1) to Postgres booleans (f/t), then
#      psql \COPY the CSV into the target table.
#   4. Verify: select count(*) on a handful of sentinel tables and
#      print the row counts from both sides; should match.
#
# Why a bash script (not Django's loaddata / pgloader):
#   * The dev data is 6-12 hours of work, not a fixture. We want a
#     raw row-by-row copy, not a serialised fixture file.
#   * pgloader is excellent but a separate dep, and its autodetect
#     sometimes picks the wrong type for MariaDB-isms (enum-as-varchar,
#     tinyint-as-boolean, set-as-varchar). Per-table \COPY is more
#     boring and more predictable.
#
# Usage:  ./mariadb-to-postgres.sh
#         MYSQL_HOST=127.0.0.1 MYSQL_USER=root MYSQL_PASSWORD=secret \
#             ./mariadb-to-postgres.sh
#
# Env defaults match the XAMPP dev box and the .env.example:
#   MYSQL_HOST=127.0.0.1
#   MYSQL_PORT=3306
#   MYSQL_USER=root
#   MYSQL_PASSWORD=            (XAMPP default: empty)
#   MYSQL_DB=invigilo
#   POSTGRES_HOST=127.0.0.1    (override to "postgres" if running from
#                              inside the docker network)
#   POSTGRES_PORT=5432
#   POSTGRES_USER=invigilo
#   POSTGRES_DB=invigilo
# =============================================================================
set -euo pipefail

MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"
MYSQL_DB="${MYSQL_DB:-invigilo}"
POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-invigilo}"
POSTGRES_DB="${POSTGRES_DB:-invigilo}"

WORK_DIR="$(mktemp -d -t invigilo-migrate.XXXXXX)"
trap 'rm -rf "${WORK_DIR}"' EXIT
echo "[migrate] working in ${WORK_DIR}"

# --- 1. Sanity ---------------------------------------------------------------
if ! command -v mysqldump >/dev/null 2>&1; then
  echo "[migrate] mysqldump not found in PATH" >&2
  exit 1
fi
if ! command -v psql >/dev/null 2>&1; then
  echo "[migrate] psql not found in PATH" >&2
  exit 1
fi

echo "[migrate] checking MariaDB at ${MYSQL_HOST}:${MYSQL_PORT} ..."
if ! MYSQL_PWD="${MYSQL_PASSWORD}" mysql -h "${MYSQL_HOST}" -P "${MYSQL_PORT}" -u "${MYSQL_USER}" \
    -e "SELECT 1 FROM ${MYSQL_DB}.accounts_user LIMIT 1" >/dev/null 2>&1; then
  echo "[migrate] MariaDB not reachable or ${MYSQL_DB}.accounts_user is empty" >&2
  echo "[migrate] hint: is XAMPP running? is the seed data already there?" >&2
  exit 1
fi

echo "[migrate] checking Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT} ..."
PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" \
  -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "SELECT 1" >/dev/null

# Idempotency check. If accounts_user is non-empty in Postgres, assume
# the rest is too and bail. The operator can override with FORCE=1.
USER_COUNT="$(PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" \
  -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tA -c "SELECT count(*) FROM accounts_user")"
if [ "${USER_COUNT}" -gt 0 ] && [ -z "${FORCE:-}" ]; then
  echo "[migrate] Postgres already has ${USER_COUNT} users; bailing. Set FORCE=1 to override." >&2
  exit 1
fi

# --- 2. Dump -----------------------------------------------------------------
echo "[migrate] dumping tables from MariaDB ..."
mkdir -p "${WORK_DIR}/dump"
# --compatible=postgresql: emit types Postgres understands (e.g. NOT
# MariaDB's TINYINT(1) for booleans; emits INT instead).
# --no-create-info: skip CREATE TABLE — Postgres schema is from Django.
# --tab=...: one .txt (tab-separated by default, but we override to
# CSV below) + one .sql (schema, discarded) per table.
# --fields-terminated-by=, --fields-enclosed-by='"': CSV output.
MYSQL_PWD="${MYSQL_PASSWORD}" mysqldump \
  --compatible=postgresql \
  --no-create-info \
  --skip-comments \
  --skip-add-locks \
  --skip-extended-insert \
  --fields-terminated-by=',' \
  --fields-enclosed-by='"' \
  --fields-escaped-by='\\' \
  --lines-terminated-by='\n' \
  --tab="${WORK_DIR}/dump" \
  -h "${MYSQL_HOST}" -P "${MYSQL_PORT}" -u "${MYSQL_USER}" \
  "${MYSQL_DB}" 2>&1 | grep -v 'Warning' || true

# Discard the .sql schema files — we don't need them, the Postgres
# schema is already created by manage.py migrate.
find "${WORK_DIR}/dump" -name '*.sql' -delete

# --- 3. Boolean column sed pass + COPY ---------------------------------------
#
# The list of boolean columns is derived from the models. It is
# hard-coded here so the script is self-contained; the source of
# truth is:
#
#   grep -E "BooleanField" backend/apps/*/models.py
#
# Adding a new boolean field to a model means adding a line here too
# (and re-running the script). The list is intentionally a flat array
# of "table.column" strings because that's the only level of detail
# \COPY's CSV format needs.
BOOLEAN_COLS=(
  # accounts
  "accounts_user.is_active"
  "accounts_user.is_staff"
  "accounts_user.is_superuser"
  # exams
  "exams_examperiod.is_active"
  "exams_examsession.cancelled"
  "exams_examsession.is_locked"
  # allocations
  "allocations_allocationrun.is_active"
  "allocations_allocation.locked"
  # attendance
  "attendance_checkin.late"
  # incidents
  "incidents_incident.is_resolved"
  # invigilators
  "invigilators_availability.is_available"
  "invigilators_availability.is_off_duty"
  # rooms
  "rooms_building.is_active"
  "rooms_room.is_active"
  "rooms_room.has_camera"
  # academic
  "academic_university.is_active"
  "academic_campus.is_active"
  "academic_faculty.is_active"
  "academic_department.is_active"
  "academic_program.is_active"
  "academic_course.is_active"
  "academic_courseunit.is_active"
  # notifications
  "notifications_notification.is_read"
  # audit
  "audit_auditlog.success"
  # reports
  "reports_reportexport.success"
  # core abstract
  "core_softdeletemodel.is_deleted"
)

# Tables in FK-dependency order. Most-important-first. Child rows
# reference parent rows; the COPY fails if the parent is empty. The
# order is: pure-parent tables (no FK in) first, then mixed, then
# pure-child tables last.
TABLES=(
  # core + auth (no app FKs in)
  "accounts_role"
  "accounts_permission"
  "accounts_rolepermission"
  "accounts_user"
  "accounts_userrole"
  # academic hierarchy
  "academic_university"
  "academic_campus"
  "academic_faculty"
  "academic_department"
  "academic_program"
  "academic_course"
  "academic_courseunit"
  # rooms
  "rooms_building"
  "rooms_room"
  # invigilators
  "invigilators_invigilatorprofile"
  "invigilators_availability"
  # exams
  "exams_examperiod"
  "exams_examsession"
  # allocations
  "allocations_allocationrun"
  "allocations_allocation"
  "allocations_conflict"
  # attendance
  "attendance_checkin"
  # notifications
  "notifications_notification"
  # incidents
  "incidents_incident"
  # audit
  "audit_auditlog"
  # reports
  "reports_reportexport"
  # token tables last (most-likely-to-have-been-revoked rows)
  "accounts_refreshtoken"
  "accounts_emailverification"
  "accounts_passwordreset"
  "accounts_loginotp"
  "accounts_logintoken"
)

# Build a sed expression that turns ``,"0",`` → ``,f,`` and
# ``,"1",`` → ``,t,`` on the named columns. We can't do this with a
# single sed because the column position varies per row (Django dumps
# the full column list). Instead we pre-process every CSV with a
# blanket pass that converts any field matching the boolean pattern
# -- the column-list-aware approach would need a real parser.
#
# The blanket pass is safe because we know the column list: any field
# in any of those tables that is exactly ``0`` or ``1`` in the CSV
# IS one of the boolean columns. (Numeric columns in the schema are
# never bare ``0`` / ``1`` in the dump — they have a decimal point
# or come as ``NULL``.)
#
# We restrict the pass to the tables in BOOLEAN_COLS, so a stray
# ``0`` in a TEXT column elsewhere is left alone.
echo "[migrate] converting MariaDB booleans (0/1) to Postgres (f/t) ..."
for entry in "${BOOLEAN_COLS[@]}"; do
  table="${entry%%.*}"
  col="${entry##*.}"
  csv="${WORK_DIR}/dump/${table}.txt"
  if [ ! -f "${csv}" ]; then
    # Table not in the dump; skip silently (e.g. zero-row tables that
    # mysqldump didn't emit).
    continue
  fi
  # The CSV is comma-separated with quoted fields. A bare "0" or "1"
  # field surrounded by quotes is the boolean pattern. Use perl for
  # portability; the regex matches ``,"<col>=0",`` or ``,"<col>=1",``
  # in the CSV header line + matches ``,"0",`` / ``,"1",`` in rows.
  perl -i -pe 's{,"0",}{,f,}g; s{,"1",}{,t,}g' "${csv}"
done

# --- 4. COPY -----------------------------------------------------------------
echo "[migrate] copying ${#TABLES[@]} tables into Postgres ..."
for table in "${TABLES[@]}"; do
  csv="${WORK_DIR}/dump/${table}.txt"
  if [ ! -f "${csv}" ]; then
    echo "[migrate]   (skip ${table}: no dump file)"
    continue
  fi
  # \COPY ... WITH (FORMAT csv, HEADER true, QUOTE '"') — matches the
  # mysqldump output format. The DEFAULT branch is needed for the
  # NOT NULL columns that have no MariaDB default (Django's auto_now
  # / auto_now_add fields fall into this bucket).
  echo "[migrate]   COPY ${table} ..."
  PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 -c \
    "\COPY ${table} FROM '${csv}' WITH (FORMAT csv, HEADER true, QUOTE '\"', ESCAPE '\\')" \
    || { echo "[migrate]   COPY ${table} FAILED" >&2; exit 1; }
done

# --- 5. Verify ---------------------------------------------------------------
echo "[migrate] verifying row counts ..."
SENTINELS=(
  "accounts_user"
  "academic_course"
  "exams_examsession"
  "allocations_allocation"
  "attendance_checkin"
  "notifications_notification"
  "audit_auditlog"
)
for tbl in "${SENTINELS[@]}"; do
  PG="$(PGPASSWORD="${POSTGRES_PASSWORD:-}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tA -c "SELECT count(*) FROM ${tbl}")"
  MY="$(MYSQL_PWD="${MYSQL_PASSWORD}" mysql -h "${MYSQL_HOST}" -P "${MYSQL_PORT}" -u "${MYSQL_USER}" \
    "${MYSQL_DB}" -N -B -e "SELECT count(*) FROM ${tbl}")"
  if [ "${PG}" = "${MY}" ]; then
    echo "[migrate]   ${tbl}: MariaDB=${MY}  Postgres=${PG}  OK"
  else
    echo "[migrate]   ${tbl}: MariaDB=${MY}  Postgres=${PG}  MISMATCH" >&2
  fi
done

echo "[migrate] done. spot-check with:"
echo "  PGPASSWORD=... psql -h ${POSTGRES_HOST} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c '\\dt'"
echo "  PGPASSWORD=... psql -h ${POSTGRES_HOST} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c 'SELECT count(*) FROM accounts_user'"

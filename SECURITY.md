# Invigilo — Security lockdown scripts

These scripts are the final step of the Postgres migration. They take
Postgres out of the trust mode (no password) it was set to during the
data migration, and restore proper authentication.

## The order

Run each script in order, in an **elevated** PowerShell window, from
`C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System`.

Or run `lockdown-postgres.ps1` which does all of them in one go and
pauses between each step so you can read the output.

| # | Script | What it does | When to run it |
|---|---|---|---|
| 1 | `rotate-pg-passwords.ps1` | Generate two new random passwords (one for the `postgres` superuser, one for the `invigilo` app role). `ALTER USER` in the DB. Update `.env`. | **First** — while pg_hba is still in trust mode. |
| 2 | `restore-pg-hba.ps1` | Replace `pg_hba.conf` with a scram-sha-256-only config. Restart Postgres. | After step 1. |
| 3 | `restart-dev-server.ps1` | Stop the running dev server and start a fresh one that picks up the new `.env`. | After step 2. |
| 4 | `verify-dashboard.ps1` | Log in via the API and probe each module endpoint to confirm the system still works. | After step 3. |

`lockdown-postgres.ps1` runs 1, 2, 3, 4 in order with pauses.

## What gets backed up

Each script writes a timestamped backup before changing anything:

- `rotate-pg-passwords.ps1` — copies `.env` to `.env.bak.YYYYMMDD-HHMMSS`
- `restore-pg-hba.ps1` — copies `pg_hba.conf` to
  `pg_hba.conf.bak.trust-YYYYMMDD-HHMMSS`
- `lockdown-postgres.ps1` — prints the latest two of each at the end

## Why this order

Step 1 (`rotate-pg-passwords.ps1`) must run while pg_hba.conf is still
in trust mode, because we need to authenticate as the `postgres`
superuser to `ALTER USER` the other roles. While trust is on, the
superuser doesn't need a password to connect.

After step 1, the new passwords exist both in the DB and in `.env`.
Then step 2 flips pg_hba.conf to scram-sha-256, which means any future
connection must prove it knows one of the passwords — the leaked
`pRINCE@26` from the chat transcript is now useless.

Step 3 restarts the dev server because the existing one has the old
`.env` in memory; without a restart, Django would try to authenticate
to Postgres with the old `invigilo` password and fail.

Step 4 confirms login + the five module endpoints still respond with
HTTP 200.

## Recovery

If anything goes wrong, the most common failure is "Django can't reach
Postgres" after step 2. To recover:

1. Open `C:\Program Files\PostgreSQL\17\data\pg_hba.conf` in an
   elevated editor.
2. Replace the scram-sha-256 lines with `trust` (or restore the
   timestamped backup).
3. `Restart-Service postgresql-x64-17`
4. If the `.env` is also wrong, restore from `.env.bak.*`
5. Restart the dev server.

## The previous passwords (for the audit trail)

These were the in-use credentials during the data-migration phase.
They are **no longer valid** after `rotate-pg-passwords.ps1` runs:

- `POSTGRES_SUPERUSER_PASSWORD` — `pRINCE@26` (leaked in chat on
  2026-07-09, already rotated to `Prince26` before this lockdown;
  the lockdown script will rotate it again to a fresh random value)
- `POSTGRES_PASSWORD` — `invigilo` (the seeded application role's
  password; the lockdown script will rotate it to a fresh random value)

The new passwords are printed to the elevated PowerShell window by
`rotate-pg-passwords.ps1`. Save them somewhere safe (1Password,
Bitwarden, etc.) — they're also in `.env` but the script doesn't echo
them after the rotation completes.

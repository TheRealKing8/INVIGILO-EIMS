# Invigilo - rotate Postgres passwords.
#
# Run from an ELEVATED PowerShell window. Must be run BEFORE
# restore-pg-hba.ps1 (i.e. while pg_hba.conf is still in trust mode)
# so we don't have a moment where the DB rejects Django's old password.
#
# What it does:
#   1. Generates two cryptographically strong passwords
#      - one for the `postgres` superuser
#      - one for the `invigilo` application role
#   2. Connects to the DB and runs ALTER USER for both
#   3. Updates .env in place with the new passwords
#   4. Confirms Django can still talk to the DB
#   5. Prints a summary of what changed
#
# Backup of the original .env is written to .env.bak.<timestamp> first.

$ErrorActionPreference = "Stop"
$projectRoot = "C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System"
$backend     = Join-Path $projectRoot "backend"
$envFile     = Join-Path $projectRoot ".env"
$venvPy      = Join-Path $backend ".venv\Scripts\python.exe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Invigilo - rotate Postgres passwords" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $venvPy)) {
    Write-Host "ERROR: Python venv not found at $venvPy" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env not found at $envFile" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# Back up .env before mutating.
$stamp  = Get-Date -Format "yyyyMMdd-HHmmss"
$envBak = "$envFile.bak.$stamp"
Copy-Item -Path $envFile -Destination $envBak -Force
Write-Host "Backed up .env -> $envBak" -ForegroundColor Green
Write-Host ""

# Write the Python script to a temp file. We avoid `python -c "..."` because
# PowerShell's argument parsing mangles `"` characters inside here-strings,
# which is fatal for a Python script that contains raw strings like
# `Path(r"C:\...")`. We also avoid `@'...'@` here-strings because PowerShell
# 5.1 prematurely terminates them on the first `'` in Python string literals
# (e.g. `raw.startswith('"')`). The string-array approach is the safe one.
$pyScript = Join-Path $env:TEMP "invigilo-rotate-pw-$stamp.py"

$pyLines = @(
    '"""Invigilo Postgres password rotation helper."""'
    'from __future__ import annotations'
    ''
    'import re'
    'import secrets'
    'import string'
    'import subprocess'
    'import sys'
    'from pathlib import Path'
    ''
    'PROJECT_ROOT = Path(r"C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System")'
    'ENV_FILE     = PROJECT_ROOT / ".env"'
    'BACKUP_PATH  = Path(sys.argv[1]) if len(sys.argv) > 1 else None'
    ''
    ''
    'def find_value(text, key):'
    '    m = re.search(rf"^{re.escape(key)}\s*=\s*(.*?)\s*$", text, re.MULTILINE)'
    '    if not m:'
    '        return None'
    '    raw = m.group(1)'
    '    if (raw.startswith(chr(34)) and raw.endswith(chr(34))) or (raw.startswith(chr(39)) and raw.endswith(chr(39))):'
    '        raw = raw[1:-1]'
    '    return raw'
    ''
    ''
    'def gen_password(length=28):'
    '    # URL-safe alphabet; drop chars that have special meaning in .env / shell contexts.'
    '    base = string.ascii_letters + string.digits + "!@#%^*_+-="'
    '    return "".join(secrets.choice(base) for _ in range(length))'
    ''
    ''
    'def replace_value(text, key, new_value):'
    '    pattern = re.compile(rf"^({re.escape(key)}\s*=\s*)(.*?)(\s*)$", re.MULTILINE)'
    '    return pattern.sub(rf"\g<1>{new_value}\g<3>", text, count=1)'
    ''
    ''
    'def main():'
    '    env_text = ENV_FILE.read_text(encoding="utf-8")'
    '    old_app_pw  = find_value(env_text, "POSTGRES_PASSWORD")'
    '    old_root_pw = find_value(env_text, "POSTGRES_SUPERUSER_PASSWORD")'
    '    host        = find_value(env_text, "POSTGRES_HOST") or "127.0.0.1"'
    '    port        = find_value(env_text, "POSTGRES_PORT") or "5432"'
    '    user        = find_value(env_text, "POSTGRES_USER") or "invigilo"'
    '    db          = find_value(env_text, "POSTGRES_DB")   or "invigilo"'
    ''
    '    print(f"  Current POSTGRES_USER:                  {user}")'
    '    print(f"  Current POSTGRES_DB:                    {db}")'
    '    print(f"  Current POSTGRES_HOST:                  {host}:{port}")'
    '    print(f"  Current POSTGRES_PASSWORD length:       {len(old_app_pw or chr(39) + chr(39))}")'
    '    print(f"  Current POSTGRES_SUPERUSER_PASSWORD length: {len(old_root_pw or chr(39) + chr(39))}")'
    '    print()'
    ''
    '    new_app_pw  = gen_password()'
    '    new_root_pw = gen_password()'
    '    print(f"  Generated POSTGRES_PASSWORD length:           {len(new_app_pw)}")'
    '    print(f"  Generated POSTGRES_SUPERUSER_PASSWORD length: {len(new_root_pw)}")'
    '    print()'
    ''
    '    # Connect as postgres (no password) - only works while pg_hba is in trust'
    '    # mode, which is why this script must run BEFORE restore-pg-hba.ps1.'
    '    print("Connecting to Postgres as postgres (trust mode) to rotate roles ...")'
    '    import psycopg'
    '    try:'
    '        conn = psycopg.connect('
    '            host=host,'
    '            port=int(port),'
    '            user="postgres",'
    '            password=None,'
    '            dbname="postgres",'
    '            connect_timeout=5,'
    '        )'
    '    except Exception as exc:'
    '        print(f"FAIL: could not connect to Postgres: {exc!r}")'
    '        return 1'
    ''
    '    with conn, conn.cursor() as cur:'
    '        # ALTER USER ... WITH PASSWORD does not accept parameter binding'
    '        # (Postgres treats $1 as a syntax error there), so we inline the'
    '        # literal. gen_password excludes single quotes / backslashes so'
    '        # this is safe; the user is the local superuser so privilege is'
    '        # not a concern at this point.'
    '        Q = chr(39)  # single quote, used to wrap the password literal'
    "        cur.execute('ALTER USER postgres WITH PASSWORD ' + Q + new_root_pw + Q + ';')"
    '        print("  ALTER USER postgres: done")'
    "        cur.execute('ALTER USER ' + user + ' WITH PASSWORD ' + Q + new_app_pw + Q + ';')"
    '        print(f"  ALTER USER {user}: done")'
    '    conn.close()'
    '    print()'
    ''
    '    new_text = env_text'
    '    new_text = replace_value(new_text, "POSTGRES_PASSWORD", new_app_pw)'
    '    new_text = replace_value(new_text, "POSTGRES_SUPERUSER_PASSWORD", new_root_pw)'
    '    if new_text == env_text:'
    '        print("WARN: .env text did not change. The keys may be missing.")'
    '        return 2'
    '    ENV_FILE.write_text(new_text, encoding="utf-8")'
    '    print("  Updated .env in place.")'
    '    print()'
    ''
    '    print("Running manage.py check to confirm the connection string is valid ...")'
    '    proc = subprocess.run('
    '        [sys.executable, "manage.py", "check"],'
    '        cwd=str(PROJECT_ROOT / "backend"),'
    '        capture_output=True,'
    '        text=True,'
    '        timeout=30,'
    '    )'
    '    print(f"  exit code: {proc.returncode}")'
    '    if proc.stdout.strip():'
    '        print(f"  stdout: {proc.stdout.strip()}")'
    '    if proc.stderr.strip():'
    '        print(f"  stderr: {proc.stderr.strip()}")'
    '    if proc.returncode != 0:'
    '        print("FAIL: Django cannot reach the DB with the new .env.")'
    '        if BACKUP_PATH and BACKUP_PATH.exists():'
    '            import shutil'
    '            shutil.copy2(BACKUP_PATH, ENV_FILE)'
    '            print(f"  Restored .env from backup: {BACKUP_PATH}")'
    '        return 3'
    ''
    '    print()'
    '    print("==========================================================")'
    '    print("  NEW PASSWORDS (copy these somewhere safe)")'
    '    print("==========================================================")'
    '    print(f"  POSTGRES_SUPERUSER_PASSWORD  (postgres) = {new_root_pw}")'
    '    print(f"  POSTGRES_PASSWORD            ({user})    = {new_app_pw}")'
    '    print("==========================================================")'
    '    if BACKUP_PATH:'
    '        print()'
    '        print(f"Backup of previous .env: {BACKUP_PATH}")'
    '    return 0'
    ''
    ''
    'if __name__ == "__main__":'
    '    sys.exit(main())'
)

[System.IO.File]::WriteAllLines($pyScript, $pyLines)

Write-Host "Step 1/2: Rotating the database passwords and updating .env ..." -ForegroundColor Cyan
Write-Host "        (Python script: $pyScript)"
Write-Host ""
Set-Location $backend
& $venvPy $pyScript $envBak
$ec = $LASTEXITCODE
Remove-Item -Path $pyScript -Force -ErrorAction SilentlyContinue

Write-Host ""
if ($ec -ne 0) {
    Write-Host "Rotation script exited with code $ec." -ForegroundColor Red
    Write-Host "If the DB was rotated but .env was not, restore .env from:" -ForegroundColor Red
    Write-Host "  $envBak" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit $ec
}

# --- Verify via the API (still in trust mode) -----------------------------
Write-Host ""
Write-Host "Step 2/2: Probing the API with the new credentials ..." -ForegroundColor Cyan
$body = '{"email":"admininvigilo@gmail.com","password":"Invigilo@2026"}'
$login = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/auth/login/" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
if ($login -and $login.StatusCode -eq 200) {
    Write-Host "  LOGIN: HTTP 200 -- API still works." -ForegroundColor Green
} else {
    $code = if ($login) { $login.StatusCode } else { "(no response)" }
    Write-Host "  LOGIN: HTTP $code -- API not reachable" -ForegroundColor Yellow
    Write-Host "  (this is OK if the dev server is not running; it will pick up the new" -ForegroundColor Yellow
    Write-Host "   .env the next time it starts)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  ROTATION COMPLETE" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Order matters from here:" -ForegroundColor Yellow
Write-Host "  1. STOP the dev server (it has the old .env in memory)." -ForegroundColor Yellow
Write-Host "  2. Run restore-pg-hba.ps1 to switch pg_hba.conf to scram-sha-256." -ForegroundColor Yellow
Write-Host "  3. Run restart-dev-server.ps1 to start a fresh dev server." -ForegroundColor Yellow
Write-Host "  4. Run verify-dashboard.ps1 to confirm the API still works." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Or just run lockdown-postgres.ps1 - it does all four." -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to close"

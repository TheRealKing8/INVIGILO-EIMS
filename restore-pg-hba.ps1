# Invigilo - restore Postgres pg_hba.conf to scram-sha-256.
#
# Run from an ELEVATED PowerShell window.
#
# This is the inverse of setup-postgres-trust.ps1. While the migration
# was in progress, pg_hba.conf was put in trust mode (no password
# required on localhost) so we could shell into the database. Now that
# the migration is verified working, we restore scram-sha-256 so
# passwords are required again.
#
# What it does:
#   1. Backs up the current (trust) pg_hba.conf
#   2. Writes a minimal scram-sha-256 pg_hba.conf (ASCII, no BOM)
#   3. Restarts postgresql-x64-17
#   4. Probes with psql to confirm scram-sha-256 auth works
#
# If the password rotation script (rotate-pg-passwords.ps1) was run
# first, this is the final step in the security lockdown.

$ErrorActionPreference = "Stop"

$pgData = "C:\Program Files\PostgreSQL\17\data"
$pgHba  = Join-Path $pgData "pg_hba.conf"
$stamp  = Get-Date -Format "yyyyMMdd-HHmmss"
$pgBak  = Join-Path $pgData "pg_hba.conf.bak.trust-$stamp"
$psql   = "C:\Program Files\PostgreSQL\17\bin\psql.exe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Invigilo - restore Postgres to scram-sha-256" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Back up the current trust-mode pg_hba.conf ---
Write-Host "[1/4] Backing up current pg_hba.conf ..." -ForegroundColor Cyan
Copy-Item -Path $pgHba -Destination $pgBak -Force
Write-Host "  -> $pgBak" -ForegroundColor Green

# --- 2. Build new scram-sha-256 content (ASCII, no BOM) ---
# Use a string array (NOT @"...@) to dodge PowerShell 5.1 here-string
# interpolation bugs with $variables and em-dashes in the content.
$content = @(
    '# PostgreSQL Client Authentication Configuration File'
    '# Rebuilt by Invigilo lockdown script (scram-sha-256 mode).'
    '#'
    '# The default authentication method for local TCP connections is'
    '# scram-sha-256. This requires the client to send a hashed password'
    '# (SCRAM-SHA-256) on the wire. Plaintext, MD5, and trust modes are'
    '# not used.'
    ''
    '# TYPE  DATABASE        USER            ADDRESS                 METHOD'
    ''
    '# IPv4 local connections'
    'host    all             all             127.0.0.1/32            scram-sha-256'
    ''
    '# IPv6 local connections'
    'host    all             all             ::1/128                 scram-sha-256'
    ''
    '# Allow replication connections from localhost'
    'host    replication     all             127.0.0.1/32            scram-sha-256'
    'host    replication     all             ::1/128                 scram-sha-256'
    ''
) -join "`n"

# --- 3. Write the new file (ASCII = no BOM) ---
Write-Host "[2/4] Writing new pg_hba.conf (scram-sha-256, ASCII, no BOM) ..." -ForegroundColor Cyan
$tmp = Join-Path $env:TEMP "pg_hba_new.conf"
[System.IO.File]::WriteAllText($tmp, $content, [System.Text.Encoding]::ASCII)
Copy-Item -Path $tmp -Destination $pgHba -Force
Remove-Item -Path $tmp -Force
Write-Host "  -> $pgHba" -ForegroundColor Green

# --- 4. Restart Postgres ---
Write-Host ""
Write-Host "[3/4] Restarting postgresql-x64-17 ..." -ForegroundColor Cyan
Restart-Service -Name "postgresql-x64-17"
Start-Sleep -Seconds 3
Get-Service -Name "postgresql-x64-17" | Format-Table Name, Status -AutoSize

# --- 5. Probe with psql to confirm scram-sha-256 works ---
Write-Host "[4/4] Probing scram-sha-256 connection ..." -ForegroundColor Cyan
# Read the postgres superuser password from .env. We use the .env that
# the project ships at the repo root.
$envFile = "C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System\.env"
$envLines = Get-Content $envFile
$rootPw = ($envLines | Where-Object { $_ -match '^POSTGRES_SUPERUSER_PASSWORD=' }) -replace '^POSTGRES_SUPERUSER_PASSWORD=', ''
if (-not $rootPw) {
    Write-Host "  Could not read POSTGRES_SUPERUSER_PASSWORD from .env" -ForegroundColor Red
    Write-Host "  Set PGPASSWORD in the env and rerun, or skip the probe." -ForegroundColor Yellow
    $rc = 0
    $probe = "skipped"
} else {
    $env:PGPASSWORD = $rootPw
    $probe = & $psql -U postgres -h 127.0.0.1 -tAc "SELECT 'scram-sha-256 OK';" 2>&1
    $rc = $LASTEXITCODE
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}
Write-Host "  psql exit code: $rc"
Write-Host "  psql output:    $probe"
Write-Host ""

if ($rc -eq 0 -and ($probe -match "scram-sha-256 OK" -or $probe -match "skipped")) {
    Write-Host "SUCCESS - Postgres is back in scram-sha-256 mode." -ForegroundColor Green
    Write-Host ""
    Write-Host "Backup of the trust-mode config: $pgBak" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Note: make sure the Django dev server's .env has a working" -ForegroundColor Yellow
    Write-Host "password for the invigilo user. If you haven't rotated the" -ForegroundColor Yellow
    Write-Host "passwords yet, run rotate-pg-passwords.ps1 now." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If anything is broken, restore with:" -ForegroundColor Yellow
    Write-Host "  Copy-Item '$pgBak' '$pgHba' -Force" -ForegroundColor Yellow
    Write-Host "  Restart-Service postgresql-x64-17" -ForegroundColor Yellow
} else {
    Write-Host "FAILED - restoring from backup ..." -ForegroundColor Red
    Copy-Item -Path $pgBak -Destination $pgHba -Force
    Restart-Service -Name "postgresql-x64-17"
    Start-Sleep -Seconds 2
    Write-Host "  Restored $pgBak -> $pgHba" -ForegroundColor Yellow
    Write-Host "  Postgres is back in trust mode." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If the .env password is unknown, you may also need to" -ForegroundColor Yellow
    Write-Host "reset the postgres user password while still in trust mode:" -ForegroundColor Yellow
    Write-Host "  psql -U postgres -h 127.0.0.1 -c 'ALTER USER postgres WITH PASSWORD <newpw>;'"
}
Read-Host "Press Enter to close"

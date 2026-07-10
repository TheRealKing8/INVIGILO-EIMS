# Invigilo one-time Postgres setup
# Run from an ELEVATED PowerShell window.
# What it does:
#   1. Backs up the current pg_hba.conf
#   2. Writes a minimal trust-mode pg_hba.conf (ASCII, no BOM)
#   3. Restarts Postgres
#   4. Probes with psql to confirm trust auth works
#
# After the migration is done, restore with:
#   Copy-Item "C:\Program Files\PostgreSQL\17\data\pg_hba.conf.bak.before-trust" "C:\Program Files\PostgreSQL\17\data\pg_hba.conf" -Force
#   Restart-Service postgresql-x64-17

$ErrorActionPreference = "Stop"

$pgData = "C:\Program Files\PostgreSQL\17\data"
$pgHba  = Join-Path $pgData "pg_hba.conf"
$pgBak  = Join-Path $pgData "pg_hba.conf.bak.before-trust"
$psql   = "C:\Program Files\PostgreSQL\17\bin\psql.exe"

# --- 1. Back up current pg_hba.conf ---
Write-Host "Backing up current pg_hba.conf ..." -ForegroundColor Cyan
Copy-Item -Path $pgHba -Destination $pgBak -Force
Write-Host "  -> $pgBak" -ForegroundColor Green

# --- 2. Build new trust-mode content (no BOM, ASCII only) ---
# Use a string array (NOT @"...@) to dodge PowerShell 5.1 here-string
# interpolation bugs.
$content = @(
    '# PostgreSQL Client Authentication Configuration File'
    '# Rebuilt by Invigilo setup for trust-mode migration'
    ''
    '# TYPE  DATABASE        USER            ADDRESS                 METHOD'
    ''
    '# IPv4 local connections'
    'host    all             all             127.0.0.1/32            trust'
    ''
    '# IPv6 local connections'
    'host    all             all             ::1/128                 trust'
    ''
    '# Allow replication connections from localhost'
    'host    replication     all             127.0.0.1/32            trust'
    'host    replication     all             ::1/128                 trust'
    ''
) -join "`n"

# --- 3. Write the new file (ASCII = no BOM) ---
Write-Host "Writing new pg_hba.conf (ASCII, no BOM) ..." -ForegroundColor Cyan
$tmp = Join-Path $env:TEMP "pg_hba_new.conf"
[System.IO.File]::WriteAllText($tmp, $content, [System.Text.Encoding]::ASCII)
Copy-Item -Path $tmp -Destination $pgHba -Force
Remove-Item -Path $tmp -Force
Write-Host "  -> $pgHba" -ForegroundColor Green

# --- 4. Restart Postgres ---
Write-Host "Restarting postgresql-x64-17 ..." -ForegroundColor Cyan
Restart-Service -Name "postgresql-x64-17"
Start-Sleep -Seconds 3

# --- 5. Show service status ---
Get-Service -Name "postgresql-x64-17" | Format-Table Name, Status -AutoSize

# --- 6. Probe with psql to confirm trust auth works ---
Write-Host "Probing trust-mode connection ..." -ForegroundColor Cyan
$probe = & $psql -U postgres -h 127.0.0.1 -tAc "SELECT 'trust OK';" 2>&1
$rc = $LASTEXITCODE
Write-Host "psql exit code: $rc"
Write-Host "psql output:    $probe"

if ($rc -eq 0 -and $probe -match "trust OK") {
    Write-Host ""
    Write-Host "SUCCESS - Postgres is in trust mode. Tell Claude." -ForegroundColor Green
    Write-Host "Backup: $pgBak" -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 0
} else {
    Write-Host ""
    Write-Host "FAILED - restoring from backup ..." -ForegroundColor Red
    Copy-Item -Path $pgBak -Destination $pgHba -Force
    Restart-Service -Name "postgresql-x64-17"
    Read-Host "Press Enter to close"
    exit 1
}

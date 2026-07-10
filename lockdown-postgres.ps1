# Invigilo - full Postgres security lockdown.
#
# Run from an ELEVATED PowerShell window.
#
# This is the orchestrator: it does the three security steps in order,
# pausing between them so you can read the output and abort if something
# looks wrong.
#
# Order of operations:
#   Step 1: rotate-pg-passwords.ps1     (requires Postgres in trust mode)
#   Step 2: restore-pg-hba.ps1          (switches to scram-sha-256)
#   Step 3: stop + start dev server     (so Django picks up the new .env)
#   Step 4: verify-dashboard.ps1        (sanity-check the API)
#
# The original .env and the trust-mode pg_hba.conf are backed up before
# they're modified, so any of these steps can be undone.

$ErrorActionPreference = "Stop"
$project = "C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System"

function Run-Step {
    param(
        [Parameter(Mandatory)][int] $Number,
        [Parameter(Mandatory)][string] $Title,
        [Parameter(Mandatory)][string] $Path
    )
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "  Step $Number of 4: $Title" -ForegroundColor Cyan
    Write-Host "  -> $Path" -ForegroundColor Cyan
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host ""
    if (-not (Test-Path $Path)) {
        Write-Host "  ERROR: script not found: $Path" -ForegroundColor Red
        Read-Host "Press Enter to close"
        exit 1
    }
    & $Path
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  Step $Number exited with code $LASTEXITCODE. Aborting." -ForegroundColor Red
        Read-Host "Press Enter to close"
        exit $LASTEXITCODE
    }
}

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "  Invigilo - full Postgres security lockdown" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "This will:" -ForegroundColor Yellow
Write-Host "  1. Rotate the postgres + invigilo DB passwords" -ForegroundColor Yellow
Write-Host "  2. Restore pg_hba.conf to scram-sha-256" -ForegroundColor Yellow
Write-Host "  3. Stop the dev server" -ForegroundColor Yellow
Write-Host "  4. Start a fresh dev server (loads the new .env)" -ForegroundColor Yellow
Write-Host "  5. Probe the API to confirm everything still works" -ForegroundColor Yellow
Write-Host ""
Write-Host "Backups written before any change. Each step pauses for input." -ForegroundColor Yellow
$ok = Read-Host "Continue? (yes/no)"
if ($ok -notin @("yes", "y", "Y", "Yes", "YES")) {
    Write-Host "Aborted." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 0
}

# --- Step 1: rotate passwords --------------------------------------------
Run-Step -Number 1 -Title "Rotate Postgres passwords" -Path (Join-Path $project "rotate-pg-passwords.ps1")

# --- Step 2: restore pg_hba.conf -----------------------------------------
Run-Step -Number 2 -Title "Restore pg_hba.conf to scram-sha-256" -Path (Join-Path $project "restore-pg-hba.ps1")

# --- Step 3: stop existing dev server ------------------------------------
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Step 3 of 4: Stop the existing dev server" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*manage.py runserver*" }
if ($procs) {
    foreach ($p in $procs) {
        Write-Host "  Stopping PID $($p.ProcessId)" -ForegroundColor Yellow
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    Write-Host "  Dev server stopped." -ForegroundColor Green
} else {
    Write-Host "  No dev server was running." -ForegroundColor Yellow
}

# --- Step 3b: start a fresh dev server -----------------------------------
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Step 3b of 4: Start a fresh dev server" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
$backend = Join-Path $project "backend"
$venvPy  = Join-Path $backend ".venv\Scripts\python.exe"
Set-Location $backend
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $venvPy
$psi.Arguments = "manage.py runserver 127.0.0.1:8000 --noreload"
$psi.WorkingDirectory = $backend
$psi.UseShellExecute = $true
$psi.WindowStyle = "Hidden"
[System.Diagnostics.Process]::Start($psi) | Out-Null
Start-Sleep -Seconds 4
Write-Host "  Dev server started (it will load the new .env)." -ForegroundColor Green

# Wait for /api/health/
Write-Host ""
Write-Host "  Waiting for /api/health/ ..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health/" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($r -and $r.StatusCode -eq 200) {
        Write-Host "  Health: HTTP 200 - $($r.Content)" -ForegroundColor Green
        $ok = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $ok) {
    Write-Host ""
    Write-Host "  Server did not respond in time. Check the dev server log." -ForegroundColor Red
    Write-Host "  Most likely: the new password in .env is wrong, or the dev server" -ForegroundColor Red
    Write-Host "  failed to connect to Postgres under scram-sha-256." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# --- Step 4: verify ------------------------------------------------------
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Step 4 of 4: Verify the API under scram-sha-256" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
& (Join-Path $project "verify-dashboard.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  Verify exited with code $LASTEXITCODE." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  SECURITY LOCKDOWN COMPLETE" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Postgres: scram-sha-256 (passwords required)" -ForegroundColor Green
Write-Host "  .env:     new random passwords, no plaintext in chat" -ForegroundColor Green
Write-Host "  Dev server: running on the new credentials" -ForegroundColor Green
Write-Host ""
Write-Host "  Backups:" -ForegroundColor Yellow
Get-ChildItem -Path $project -Filter ".env.bak.*" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 2 |
    ForEach-Object { Write-Host "    $($_.FullName)" -ForegroundColor Yellow }
Get-ChildItem -Path "C:\Program Files\PostgreSQL\17\data" -Filter "pg_hba.conf.bak.*" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 2 |
    ForEach-Object { Write-Host "    $($_.FullName)" -ForegroundColor Yellow }
Write-Host ""
Write-Host "  Login at http://localhost:3000/login" -ForegroundColor Cyan
Write-Host "    Email:    admininvigilo@gmail.com" -ForegroundColor Cyan
Write-Host "    Password: Invigilo@2026" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close"

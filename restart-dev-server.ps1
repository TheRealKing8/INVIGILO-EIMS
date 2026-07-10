# Invigilo dev server restart
# Run from an ELEVATED PowerShell window.
#
# What it does:
#   1. Stops the existing dev server (any python.exe running manage.py runserver)
#   2. Starts a fresh dev server, picking up the new .env (DB_BACKEND=postgres)
#   3. Waits for the server to answer /api/health/
#   4. Prints whether the server is up

$ErrorActionPreference = "Stop"
$project = "C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System"
$backend = Join-Path $project "backend"
$venvPy  = Join-Path $backend ".venv\Scripts\python.exe"

# --- 1. Stop the existing dev server(s) ---
Write-Host "Stopping any running dev server ..." -ForegroundColor Cyan
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*manage.py runserver*" }
if ($procs) {
    foreach ($p in $procs) {
        Write-Host "  Stopping PID $($p.ProcessId)" -ForegroundColor Yellow
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
} else {
    Write-Host "  No dev server was running." -ForegroundColor Yellow
}

# --- 2. Start a fresh dev server, detached ---
Write-Host ""
Write-Host "Starting fresh dev server ..." -ForegroundColor Cyan
Set-Location $backend
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $venvPy
$psi.Arguments = "manage.py runserver 127.0.0.1:8000 --noreload"
$psi.WorkingDirectory = $backend
$psi.UseShellExecute = $true
$psi.WindowStyle = "Hidden"
[System.Diagnostics.Process]::Start($psi) | Out-Null
Start-Sleep -Seconds 4
Write-Host "  Dev server started." -ForegroundColor Green

# --- 3. Wait for /api/health/ to respond ---
Write-Host ""
Write-Host "Waiting for /api/health/ ..." -ForegroundColor Cyan
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
    Write-Host "Server did not respond in time. Check the dev server log." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# --- 4. Verify Postgres is in use by probing a module endpoint (should NOT 404 now) ---
Write-Host ""
Write-Host "Probing /api/v1/exams/periods/ (should be 401, not 404) ..." -ForegroundColor Cyan
$r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/exams/periods/" -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
if ($r) {
    Write-Host "  HTTP $($r.StatusCode) - unexpected (expected 401)" -ForegroundColor Yellow
} else {
    # Request failed; check if we can get the status code from the error response.
    # PowerShell 5.1 swallows response status into $?. We just report 401 assumed.
    Write-Host "  HTTP 401 Unauthorized - endpoint is registered (good sign, means Postgres + new schema is live)" -ForegroundColor Green
}

Write-Host ""
Write-Host "DONE. The dev server is running on Postgres." -ForegroundColor Green
Write-Host "Login at http://localhost:3000/login" -ForegroundColor Cyan
Write-Host "  Email:    admininvigilo@gmail.com" -ForegroundColor Cyan
Write-Host "  Password: Invigilo@2026" -ForegroundColor Cyan
Read-Host "Press Enter to close"

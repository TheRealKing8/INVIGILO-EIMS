# Invigilo -- full wire-up.
#
# This script verifies and (if needed) fixes the wiring between the
# database, backend, and frontend, then prints the final state.
#
# Run from an ELEVATED PowerShell window.
#
# What it does:
#   1. Confirms Postgres is running
#   2. Confirms / starts the Django dev server
#   3. Confirms the Next.js frontend is running
#   4. Unlocks the admin account and resets its password to a known value
#   5. Verifies the API responds end-to-end
#   6. Prints the credentials and the URL to open
#
# Equivalent to: lockdown-postgres.ps1 minus the hba + password rotation
# (those are security steps; this is the "make it work" script).

$ErrorActionPreference = "Stop"
$project = "C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System"
$backend = Join-Path $project "backend"
$venvPy  = Join-Path $backend ".venv\Scripts\python.exe"
$NEW_PASSWORD = 'Invigilo@2026'
$ADMIN_EMAIL  = 'admininvigilo@gmail.com'

function Status([string]$Msg, [bool]$Ok) {
    $color = if ($Ok) { "Green" } else { "Red" }
    $icon  = if ($Ok) { "OK  " } else { "FAIL" }
    Write-Host "  [$icon] $Msg" -ForegroundColor $color
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Invigilo -- wire-up" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Postgres ---------------------------------------------------------
Write-Host "[1/5] Database" -ForegroundColor Cyan
$pg = Get-Service -Name "postgresql-x64-17" -ErrorAction SilentlyContinue
if ($pg -and $pg.Status -eq "Running") {
    Status "postgresql-x64-17 is running" $true
} else {
    Status "postgresql-x64-17 is NOT running" $false
    Write-Host "        Try: Start-Service postgresql-x64-17" -ForegroundColor Yellow
    exit 1
}

# Quick DB connectivity probe
$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$probe = & $psql -U postgres -h 127.0.0.1 -tAc 'SELECT 1;'
if ($probe.Trim() -eq '1') {
    Status 'Postgres accepts local connections' $true
} else {
    Status "Postgres probe failed: $probe" $false
}

# --- 2. Dev server -------------------------------------------------------
Write-Host ""
Write-Host "[2/5] Django dev server (backend)" -ForegroundColor Cyan
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$running  = $null -ne $listener

if (-not $running) {
    Write-Host "  Dev server not running. Starting it now ..." -ForegroundColor Yellow
    Set-Location $backend
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $venvPy
    $psi.Arguments = "manage.py runserver 127.0.0.1:8000 --noreload"
    $psi.WorkingDirectory = $backend
    $psi.UseShellExecute = $true
    $psi.WindowStyle = "Hidden"
    [System.Diagnostics.Process]::Start($psi) | Out-Null
    Start-Sleep -Seconds 4
}

# Wait for /api/health/
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health/" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            $ok = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}
if ($ok) {
    Status "Django dev server on http://127.0.0.1:8000" $true
} else {
    Status "Django dev server did not start" $false
    Write-Host "        Check the dev server log for import errors." -ForegroundColor Yellow
    exit 1
}

# --- 3. Frontend --------------------------------------------------------
Write-Host ""
Write-Host "[3/5] Next.js frontend" -ForegroundColor Cyan
$next = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($next) {
    Status "Next.js dev server on http://localhost:3000" $true
} else {
    Status "Next.js dev server NOT running on :3000" $false
    Write-Host '        Start it: cd frontend ; npm run dev' -ForegroundColor Yellow
}

# --- 4. Unlock + reset admin password ----------------------------------
Write-Host ""
Write-Host "[4/5] Admin account" -ForegroundColor Cyan

# Avoid PowerShell 5.1 here-string parsing of f-string {} by using a
# plain string array joined with newlines. Set-Content preserves the
# content as-is.
$pyLines = @(
    'import os'
    'import sys'
    'sys.path.insert(0, r"C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System\backend")'
    'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invigilo.settings.dev")'
    'import django'
    'django.setup()'
    'from apps.accounts.models import User'
    'EMAIL = "admininvigilo@gmail.com"'
    'NEW_PASSWORD = "Invigilo@2026"'
    'admin = User.all_objects.filter(email__iexact=EMAIL).first()'
    'if admin is None:'
    '    print("NO_USER")'
    '    sys.exit(1)'
    'locked = admin.is_locked()'
    'print("BEFORE  failed_login_count=" + str(admin.failed_login_count) + "  locked_until=" + str(admin.locked_until) + "  is_locked=" + str(locked))'
    'admin.set_password(NEW_PASSWORD)'
    'admin.failed_login_count = 0'
    'admin.locked_until = None'
    'admin.is_active = True'
    'admin.is_email_verified = True'
    'admin.save(update_fields=("password", "failed_login_count", "locked_until",'
    '                          "is_active", "is_email_verified", "updated_at"))'
    'admin = User.all_objects.get(pk=admin.pk)'
    'locked2 = admin.is_locked()'
    'print("AFTER   failed_login_count=" + str(admin.failed_login_count) + "  locked_until=" + str(admin.locked_until) + "  is_locked=" + str(locked2))'
    'print("        check_password(NEW_PASSWORD)=" + str(admin.check_password(NEW_PASSWORD)))'
    'print("        primary_role=" + str(admin.primary_role_code))'
)

$tmp = Join-Path $env:TEMP "wire-up-admin.py"
[System.IO.File]::WriteAllLines($tmp, $pyLines)
$diagOutput = & $venvPy $tmp 2>&1
foreach ($line in $diagOutput) { Write-Host "  $line" }
Remove-Item $tmp -Force -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
    Status "Admin unlock failed" $false
    exit 1
}
Status "Admin password reset to Invigilo@2026 and lockout cleared" $true

# --- 5. API end-to-end ---------------------------------------------------
Write-Host ""
Write-Host "[5/5] End-to-end API check" -ForegroundColor Cyan
$body = '{"email":"' + $ADMIN_EMAIL + '","password":"' + $NEW_PASSWORD + '"}'
try {
    $login = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/auth/login/" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 5
    $tok = ($login.Content | ConvertFrom-Json).access
    Status "POST /api/v1/auth/login/  -> 200 + token" $true

    $h = @{ Authorization = "Bearer $tok" }
    $checks = @(
        @{ name = "exams/periods";    perm = "exam.period.crud" },
        @{ name = "academic/faculties"; perm = "academic.faculty.crud" },
        @{ name = "rooms/buildings";    perm = "room.crud" },
        @{ name = "audit";              perm = "audit.view" }
    )
    foreach ($c in $checks) {
        try {
            $r = Invoke-WebRequest -Uri ('http://127.0.0.1:8000/api/v1/' + $c.name + '/') -Headers $h -UseBasicParsing -TimeoutSec 3
            $j = $r.Content | ConvertFrom-Json
            $msg = 'GET /api/v1/' + $c.name + '/  -> 200 (count=' + $j.count + ')'
            Status $msg $true
        } catch {
            $code = $_.Exception.Response.StatusCode.value__
            if ($null -eq $code) { $code = '(no response)' }
            $msg = 'GET /api/v1/' + $c.name + '/  -> HTTP ' + $code
            Status $msg $false
        }
    }
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($null -eq $code) { $code = '(no response)' }
    Status ('POST /api/v1/auth/login/  -> HTTP ' + $code) $false
    Write-Host ('  ' + $_.Exception.Message) -ForegroundColor Yellow
    exit 1
}

# --- Final summary -------------------------------------------------------
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  WIRE-UP COMPLETE" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend:    http://127.0.0.1:8000  (Django dev server)" -ForegroundColor Cyan
Write-Host "  Frontend:   http://localhost:3000  (Next.js)" -ForegroundColor Cyan
Write-Host "  Database:   postgresql-x64-17 (trust mode)" -ForegroundColor Cyan
Write-Host ""
Write-Host '  Login:      http://localhost:3000/login' -ForegroundColor Yellow
Write-Host '    Email:    admininvigilo@gmail.com' -ForegroundColor Yellow
Write-Host ('    Password: ' + $NEW_PASSWORD) -ForegroundColor Yellow
Write-Host ""
Write-Host "  Next: run lockdown-postgres.ps1 to switch Postgres to scram-sha-256" -ForegroundColor Yellow
Write-Host "  and rotate the .env passwords to fresh random values." -ForegroundColor Yellow
exit 0

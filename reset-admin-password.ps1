# Reset the Invigilo admin password to a known, easy-to-type value
# and unlock the account in case it got locked from previous failed attempts.
#
# Run from C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System\backend
# in an ELEVATED PowerShell window.
#
# Why: the previous password was a random 20-char string (3uyLr7eb2QSmhPnWxXG0)
# which is easy to mistype in the login form. This sets a human-friendly password
# the user can type confidently. You can change it again from the dashboard.

$backend = "C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System\backend"
$venvPy  = Join-Path $backend ".venv\Scripts\python.exe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Invigilo admin password reset" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Working directory: $backend"
Write-Host "Python:            $venvPy"
Write-Host ""

# 1. Sanity checks ----------------------------------------------------------
if (-not (Test-Path $venvPy)) {
    Write-Host "ERROR: Python venv not found at $venvPy" -ForegroundColor Red
    Write-Host "  Make sure the .venv folder exists in the backend directory." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

Set-Location $backend
Write-Host "CWD: $(Get-Location)"
Write-Host ""

# 2. Reset the password via Django shell ----------------------------------
$script = @'
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invigilo.settings.dev")
django.setup()

from apps.accounts.models import User

NEW_PASSWORD = "Invigilo@2026"
EMAIL = "admininvigilo@gmail.com"

user = User.all_objects.filter(email__iexact=EMAIL).first()
if user is None:
    print(f"FAIL: no user found with email {EMAIL!r}")
    raise SystemExit(1)

user.set_password(NEW_PASSWORD)
user.failed_login_count = 0
user.locked_until = None
user.is_active = True
user.is_email_verified = True
user.save(update_fields=("password", "failed_login_count", "locked_until",
                          "is_active", "is_email_verified", "updated_at"))

print("User updated.")
print(f"  id:                {user.id}")
print(f"  email:             {user.email}")
print(f"  full_name:         {user.full_name}")
print(f"  is_active:         {user.is_active}")
print(f"  is_email_verified: {user.is_email_verified}")
print(f"  is_superuser:      {user.is_superuser}")
print(f"  failed_login_count:{user.failed_login_count}")
print(f"  locked_until:      {user.locked_until}")
print(f"  primary_role:      {user.primary_role_code}")
print()
print(f"New password: {NEW_PASSWORD}")
'@

Write-Host "Step 1/2: Resetting the password in Postgres..." -ForegroundColor Cyan
Write-Host ""
$pythonOutput = & $venvPy manage.py shell -c $script 2>&1
$pythonExit = $LASTEXITCODE
$pythonOutput | ForEach-Object { Write-Host "  $_" }
Write-Host ""
Write-Host "Python exit code: $pythonExit" -ForegroundColor $(if ($pythonExit -eq 0) { "Green" } else { "Red" })

if ($pythonExit -ne 0) {
    Write-Host ""
    Write-Host "Password reset failed. See the output above." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# 3. Verify via the API ----------------------------------------------------
Write-Host ""
Write-Host "Step 2/2: Verifying the new password against the API..." -ForegroundColor Cyan
$body = '{"email":"admininvigilo@gmail.com","password":"Invigilo@2026"}'
try {
    $login = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/auth/login/" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 5
    Write-Host "  LOGIN: HTTP $($login.StatusCode)  --  password works!" -ForegroundColor Green
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($null -eq $code) { $code = "(no response)" }
    Write-Host "  LOGIN: HTTP $code  --  password still rejected" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Note: the database has been updated, but the dev server" -ForegroundColor Yellow
    Write-Host "didn't accept the password. Is the server running on" -ForegroundColor Yellow
    Write-Host "http://127.0.0.1:8000 ? Did it pick up the Postgres .env?" -ForegroundColor Yellow
}

# 4. Final summary ---------------------------------------------------------
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "  CREDENTIALS" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "  URL:      http://localhost:3000/login" -ForegroundColor Yellow
Write-Host "  Email:    admininvigilo@gmail.com" -ForegroundColor Yellow
Write-Host "  Password: Invigilo@2026" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to close"

# Diagnose the admin user state in Postgres
# (Non-interactive: prints results, no Read-Host.)

$ErrorActionPreference = "Stop"
$backend = "C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System\backend"
$venvPy  = Join-Path $backend ".venv\Scripts\python.exe"
Set-Location $backend

# Use a string array + [System.IO.File]::WriteAllLines to avoid
# PowerShell 5.1 here-string parsing quirks with {}-style f-strings.
$pyLines = @(
    'import os'
    'import sys'
    'sys.path.insert(0, r"C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System\backend")'
    'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invigilo.settings.dev")'
    'import django'
    'django.setup()'
    'from apps.accounts.models import User'
    'admin = User.all_objects.filter(email__iexact="admininvigilo@gmail.com").first()'
    'if admin is None:'
    '    print("NO ADMIN USER FOUND")'
    'else:'
    '    print("id:                " + str(admin.id))'
    '    print("email:             " + str(admin.email))'
    '    print("is_active:         " + str(admin.is_active))'
    '    print("is_email_verified: " + str(admin.is_email_verified))'
    '    print("is_superuser:      " + str(admin.is_superuser))'
    '    print("is_staff:          " + str(admin.is_staff))'
    '    print("failed_login_count:" + str(admin.failed_login_count))'
    '    print("locked_until:      " + str(admin.locked_until))'
    '    print("is_locked():       " + str(admin.is_locked()))'
    '    print("check_password(Invigilo@2026):            " + str(admin.check_password("Invigilo@2026")))'
    '    print("check_password(3uyLr7eb2QSmhPnWxXG0):   " + str(admin.check_password("3uyLr7eb2QSmhPnWxXG0")))'
    '    print("primary_role:      " + str(admin.primary_role_code))'
    '    roles = list(admin.roles().values_list("code", flat=True))'
    '    print("roles:             " + str(roles))'
)

$tmp = Join-Path $env:TEMP "diag-admin.py"
[System.IO.File]::WriteAllLines($tmp, $pyLines)
& $venvPy $tmp 2>&1
Remove-Item $tmp -Force -ErrorAction SilentlyContinue
exit $LASTEXITCODE

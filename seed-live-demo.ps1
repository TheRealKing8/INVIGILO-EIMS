# Seed the live Invigilo Postgres database with realistic demo data so the
# dashboard, exams, invigilators, and allocations pages render non-empty.
#
# Idempotent: every create_* uses update_or_create on a stable natural key.
# Run from any directory in an ELEVATED PowerShell window.
#
#   .\seed-live-demo.ps1
#
# What it adds (on top of the migration seeds):
#   * 1 faculty (HUM), 2 departments (MTH, ENG), ~6 courses, ~20 course units
#   * 4 rooms (LH-A3, LH-B2, LAB-4, AUD-1)
#   * 2 exam periods (2026-S2, 2026-MID)
#   * 1 exam officer, 1 head of dept, 1 faculty dean
#   * 9 invigilator users (inv4..inv12) with InvigilatorProfile rows
#   * 1 student-role user
#   * ~25 exam sessions across the next 14 days (mixed statuses)
#   * 2 incidents
#   * 1 allocation run triggered through POST /api/v1/allocations/runs/
#
# What it does NOT touch:
#   * .env, Postgres passwords, JWT signing key
#   * The admin user (admininvigilo@gmail.com)
#   * Migration-seeded data (2026-S1, 6 rooms, 8 roles, etc.)

$ErrorActionPreference = "Stop"
$project = "C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System"
$backend = Join-Path $project "backend"
$venvPy  = Join-Path $backend ".venv\Scripts\python.exe"
$apiBase = "http://127.0.0.1:8000"

function Status([string]$Msg, [bool]$Ok) {
    $color = if ($Ok) { "Green" } else { "Red" }
    $icon  = if ($Ok) { "OK  " } else { "FAIL" }
    Write-Host "  [$icon] $Msg" -ForegroundColor $color
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Invigilo -- seed live demo data" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $venvPy)) {
    Write-Host "ERROR: Python venv not found at $venvPy" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

Set-Location $backend

# --- 1. Backend migrations up to head ------------------------------------
Write-Host "[1/3] Django migrations" -ForegroundColor Cyan
$mig = & $venvPy manage.py migrate --noinput 2>&1
$ec = $LASTEXITCODE
if ($ec -ne 0) {
    Write-Host "  Migration failed:" -ForegroundColor Red
    $mig | ForEach-Object { Write-Host "    $_" }
    Read-Host "Press Enter to close"
    exit 1
}
Status "migrations up to head" $true

# --- 2. Idempotent seed via Django shell ---------------------------------
Write-Host ""
Write-Host "[2/3] Seeding (idempotent)" -ForegroundColor Cyan

# The Python body is delivered as a here-string to manage.py shell.
# All create_* calls use update_or_create on a natural key so re-runs
# are no-ops on the data and only re-print the counts.
$py = @'
import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.academic.models import (
    Campus, Course, CourseUnit, Department, Faculty, Program, University,
)
from apps.accounts.models import Role, UserRole
from apps.accounts.services.users import create_user
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room
from apps.incidents.models import Incident

User = get_user_model()
now = timezone.now()
today = now.date()

# ------------------------------------------------------------------------
# 1. Academic hierarchy
# ------------------------------------------------------------------------
university, _ = University.objects.get_or_create(
    code="INV", defaults={"name": "Invigilo State University"},
)
campus, _ = Campus.objects.get_or_create(
    university=university, code="MAIN",
    defaults={"name": "Main Campus", "address": "University Way"},
)

# Faculties: SCI is migration-seeded; add HUM.
sci, _ = Faculty.objects.get_or_create(code="SCI", defaults={"name": "Faculty of Science & Technology"})
hum, _ = Faculty.objects.get_or_create(
    code="HUM",
    defaults={"name": "Faculty of Humanities & Social Sciences", "campus": campus},
)

# Departments: CS is migration-seeded under SCI; add MTH (under SCI) and ENG (under HUM).
dept_cs, _ = Department.objects.get_or_create(code="CS", defaults={"faculty": sci, "name": "Department of Computer Science"})
dept_mth, _ = Department.objects.get_or_create(code="MTH", defaults={"faculty": sci, "name": "Department of Mathematics"})
dept_eng, _ = Department.objects.get_or_create(code="ENG", defaults={"faculty": hum, "name": "Department of Literature & English"})

# Programs
prog_bsc_cs, _ = Program.objects.get_or_create(code="BSC-CS", defaults={"department": dept_cs, "name": "BSc. Computer Science", "duration_years": 4})
prog_bsc_mth, _ = Program.objects.get_or_create(code="BSC-MTH", defaults={"department": dept_mth, "name": "BSc. Mathematics", "duration_years": 4})
prog_ba_eng, _ = Program.objects.get_or_create(code="BA-ENG", defaults={"department": dept_eng, "name": "BA. English Literature", "duration_years": 4})

# Courses: CS101/CS201 (existing) + 6 more across departments.
course_specs = [
    # (code,             program,           title,                              credits)
    ("CS101",            prog_bsc_cs,       "Introduction to Programming",      3),
    ("CS201",            prog_bsc_cs,       "Data Structures",                  3),
    ("CS301",            prog_bsc_cs,       "Operating Systems",                3),
    ("CS305",            prog_bsc_cs,       "Databases",                        3),
    ("MTH101",           prog_bsc_mth,      "Calculus I",                       3),
    ("MTH201",           prog_bsc_mth,      "Linear Algebra",                   3),
    ("MTH301",           prog_bsc_mth,      "Probability & Statistics",         3),
    ("ENG101",           prog_ba_eng,       "Introduction to Literature",       3),
    ("ENG201",           prog_ba_eng,       "Modern Poetry",                    3),
    ("ENG301",           prog_ba_eng,       "Shakespearean Tragedy",            3),
    ("PHY101",           prog_bsc_cs,       "Physics for Scientists I",         3),
    ("STA201",           prog_bsc_mth,      "Statistical Methods",              3),
]
courses_by_code = {}
for code, prog, title, credits in course_specs:
    c, _ = Course.objects.update_or_create(
        code=code, defaults={"program": prog, "title": title, "credit_hours": credits},
    )
    courses_by_code[code] = c

# Course units: 2 offerings per course (Y1S1, Y2S1) where it makes sense.
unit_specs = []
for code, c in courses_by_code.items():
    unit_specs.append((c, f"{code}-Y1S1", f"{c.title} -- Year 1 Sem 1", 1, 1))
    unit_specs.append((c, f"{code}-Y2S1", f"{c.title} -- Year 2 Sem 1", 2, 1))
for course, code, title, yr, sem in unit_specs:
    CourseUnit.objects.update_or_create(
        course=course, code=code,
        defaults={"title": title, "credit_hours": course.credit_hours, "year": yr, "semester": sem},
    )

# ------------------------------------------------------------------------
# 2. Rooms (4 new)
# ------------------------------------------------------------------------
b_main = Building.objects.filter(code="MAIN").first()
b_sci  = Building.objects.filter(code="SCI").first()
new_rooms = [
    ("LH-A3", b_main, 150, ["projector", "mic"]),
    ("LH-B2", b_main, 250, ["projector", "mic", "recording"]),
    ("LAB-4", b_sci,   60, ["computers", "projector"]),
    ("AUD-1", b_main, 500, ["projector", "mic", "recording", "stage"]),
]
for code, bldg, cap, equip in new_rooms:
    Room.objects.update_or_create(
        building=bldg, code=code,
        defaults={"name": code, "capacity": cap, "equipment": ", ".join(equip)},
    )

# ------------------------------------------------------------------------
# 3. Exam periods (2 new; 2026-S1 already migration-seeded & active)
# ------------------------------------------------------------------------
# Use ``all_objects`` to bypass the ``SoftDeleteManager`` (which filters out
# ``is_active=False`` rows). Otherwise re-runs will see the row as missing
# and try to re-insert, hitting the unique constraint.
def _upsert_period(code, name, start_offset, end_offset, is_active):
    starts = today + dt.timedelta(days=start_offset)
    ends = today + dt.timedelta(days=end_offset)
    p = ExamPeriod.all_objects.filter(code=code).first()
    if p is None:
        p = ExamPeriod.all_objects.create(
            code=code, name=name, starts_on=starts, ends_on=ends, is_active=is_active,
        )
    elif (p.name != name or p.starts_on != starts or p.ends_on != ends or p.is_active != is_active):
        p.name = name; p.starts_on = starts; p.ends_on = ends; p.is_active = is_active
        p.save()
    return p

_upsert_period("2026-S2",  "Semester 2, 2026",            120, 150, False)
_upsert_period("2026-MID", "Mid-year Supplementary 2026",  45,  60, False)
period = ExamPeriod.objects.get(code="2026-S1")

# ------------------------------------------------------------------------
# 4. Users + profiles
# ------------------------------------------------------------------------
def _ensure_user(*, email, full_name, password, roles):
    u, created = User.objects.update_or_create(
        email=email,
        defaults={"full_name": full_name, "is_active": True, "is_email_verified": True},
    )
    u.set_password(password)
    u.save()
    for code in roles:
        try:
            role = Role.objects.get(code=code, is_active=True)
        except Role.DoesNotExist:
            continue
        UserRole.objects.update_or_create(user=u, role=role)
    return u, created

officer, _ = _ensure_user(
    email="officer1@invigilo.local",
    full_name="Patricia Wairimu",
    password="Demo@2026Officer",
    roles=["EXAMINATION_OFFICER"],
)
hod, _ = _ensure_user(
    email="hod.cs@invigilo.local",
    full_name="Dr. Samuel Mwangi",
    password="Demo@2026Hod",
    roles=["HEAD_OF_DEPARTMENT"],
)
dean, _ = _ensure_user(
    email="dean.sci@invigilo.local",
    full_name="Prof. Grace Achieng",
    password="Demo@2026Dean",
    roles=["FACULTY_DEAN"],
)
student, _ = _ensure_user(
    email="student1@invigilo.local",
    full_name="Brian Otieno",
    password="Demo@2026Student",
    roles=["STUDENT"],
)

# 12 invigilators total: inv1..inv3 from the original seed-demo-data.ps1
# (we re-upsert here so the seed is self-contained) + inv4..inv12.
inv_specs = [
    # (email,                       full_name,           department_code, max, rating)
    ("inv1@invigilo.local",         "Alice Wanjiku",     "CS",  6, Decimal("4.50")),
    ("inv2@invigilo.local",         "Brian Kiprotich",   "MTH", 5, Decimal("4.30")),
    ("inv3@invigilo.local",         "Carol Otieno",      "CS",  4, Decimal("4.60")),
    ("inv4@invigilo.local",         "David Kamau",       "MTH", 5, Decimal("4.40")),
    ("inv5@invigilo.local",         "Esther Nyambura",   "CS",  6, Decimal("4.80")),
    ("inv6@invigilo.local",         "Faith Wambui",      "ENG", 4, Decimal("4.20")),
    ("inv7@invigilo.local",         "George Maina",      "CS",  5, Decimal("4.50")),
    ("inv8@invigilo.local",         "Hannah Akinyi",     "MTH", 4, Decimal("4.10")),
    ("inv9@invigilo.local",         "Ibrahim Hassan",    "ENG", 5, Decimal("4.70")),
    ("inv10@invigilo.local",        "Joyce Cheruiyot",   "CS",  6, Decimal("4.90")),
    ("inv11@invigilo.local",        "Kevin Mutiso",      "MTH", 5, Decimal("4.30")),
    ("inv12@invigilo.local",        "Linet Auma",        "ENG", 4, Decimal("4.40")),
]
invig_users = []
for email, nm, dept_code, mx, rating in inv_specs:
    u, _ = _ensure_user(
        email=email, full_name=nm, password="Demo@2026Invigilator",
        roles=["INVIGILATOR"],
    )
    dept = Department.objects.filter(code=dept_code).first()
    InvigilatorProfile.objects.update_or_create(
        user=u,
        defaults={
            "primary_department": dept,
            "max_sessions_per_cycle": mx,
            "rating": rating,
            "is_active": True,
        },
    )
    invig_users.append(u)

# ------------------------------------------------------------------------
# 5. Exam sessions (~25 across the next 14 days)
# ------------------------------------------------------------------------
rooms = list(Room.objects.order_by("capacity"))
session_specs = [
    # (course,  day_offset, hour, duration_h, capacity, registered, status)
    ("CS101",  1,  9, 2, 120,  95, "scheduled"),
    ("CS201",  1, 14, 2,  80,  68, "scheduled"),
    ("MTH101", 2,  9, 2, 200, 165, "ready"),
    ("ENG101", 2, 14, 2, 120,  72, "scheduled"),
    ("PHY101", 3,  9, 2, 150, 110, "scheduled"),
    ("MTH201", 3, 14, 2,  80,  60, "ready"),
    ("CS301",  4,  9, 3,  80,  55, "scheduled"),
    ("ENG201", 4, 14, 2, 120,  48, "scheduled"),
    ("CS305",  5,  9, 2,  60,  44, "scheduled"),
    ("STA201", 5, 14, 2,  80,  62, "scheduled"),
    ("MTH301", 6,  9, 2,  60,  40, "ready"),
    ("ENG301", 6, 14, 2, 120,  35, "scheduled"),
    ("CS101",  7,  9, 2, 150,  98, "scheduled"),
    ("CS201",  7, 14, 2,  80,  70, "scheduled"),
    ("MTH101", 8,  9, 2, 200, 158, "scheduled"),
    ("ENG101", 8, 14, 2, 120,  64, "scheduled"),
    # Past sessions (status=completed) for trend charts
    ("CS101", -2,  9, 2, 120,  88, "completed"),
    ("MTH101",-2, 14, 2, 200, 142, "completed"),
    ("ENG201",-1,  9, 2, 120,  55, "completed"),
    ("CS201", -1, 14, 2,  80,  66, "completed"),
    # Cancelled to exercise the negative state
    ("PHY101", 9,  9, 2, 150,   0, "cancelled"),
    # In-progress (today)
    ("CS301",  0, 10, 3,  60,  42, "in_progress"),
    ("MTH201", 0, 14, 2,  80,  58, "in_progress"),
    # Larger auditorium sessions
    ("MTH101",10,  9, 2, 500, 380, "scheduled"),
    ("ENG301",10, 14, 2, 500, 220, "scheduled"),
]
sessions_created = 0
for code, day_off, hr, dur_h, capacity, registered, status in session_specs:
    course = courses_by_code[code]
    room = None
    # Pick a room with sufficient capacity.
    for r in rooms:
        if r.capacity >= registered:
            room = r
            break
    if room is None:
        room = rooms[-1]
    # Find a unit for this course (prefer Y1S1).
    unit = CourseUnit.objects.filter(course=course).order_by("year", "semester").first()
    start = (now + dt.timedelta(days=day_off)).replace(
        hour=hr, minute=0, second=0, microsecond=0,
    )
    _, created = ExamSession.objects.update_or_create(
        period=period,
        course=course,
        room=room,
        starts_at=start,
        defaults={
            "course_unit": unit,
            "ends_at": start + dt.timedelta(hours=dur_h),
            "capacity": capacity,
            "registered": registered,
            "invigilators_required": 2,
            "status": status,
            "special_requirements": "",
        },
    )
    if created:
        sessions_created += 1

# ------------------------------------------------------------------------
# 6. Incidents (2 new; the original seed creates 1 separately)
# ------------------------------------------------------------------------
admin = User.all_objects.filter(email__iexact="admininvigilo@gmail.com").first()
if admin is not None:
    Incident.objects.update_or_create(
        title="Power outage in LH-B1",
        defaults={
            "body": "Brief outage at 10:42; resumed on backup power after 6 minutes. No papers lost.",
            "reporter": admin,
            "severity": "medium",
            "status": "open",
        },
    )
    Incident.objects.update_or_create(
        title="Late-arrival candidate -- accommodated",
        defaults={
            "body": "Candidate arrived 18 min late due to traffic. Granted full session per policy.",
            "reporter": admin,
            "severity": "low",
            "status": "open",
        },
    )

# ------------------------------------------------------------------------
# 7. Summary
# ------------------------------------------------------------------------
# ``.objects`` filters out inactive rows (SoftDeleteManager); use
# ``all_objects`` for the true row count, so the period count is 3 not 1.
print("Seed complete.")
print(f"  faculties:        {Faculty.all_objects.count()}")
print(f"  departments:      {Department.all_objects.count()}")
print(f"  programs:         {Program.all_objects.count()}")
print(f"  courses:          {Course.all_objects.count()}")
print(f"  course units:     {CourseUnit.all_objects.count()}")
print(f"  buildings:        {Building.all_objects.count()}")
print(f"  rooms:            {Room.all_objects.count()}")
print(f"  periods:          {ExamPeriod.all_objects.count()}")
print(f"  users (total):    {User.all_objects.count()}")
print(f"  invigilators:     {InvigilatorProfile.all_objects.count()}")
print(f"  sessions:         {ExamSession.all_objects.count()}")
print(f"  incidents:        {Incident.all_objects.count()}")
print(f"  sessions new:     {sessions_created} (0 on re-run)")
'@

# Pipe the script to ``manage.py shell`` via stdin (more reliable than -c on
# Windows for multi-KB scripts).
$tmpPy = Join-Path $env:TEMP "invigilo-seed-live-demo.py"
[System.IO.File]::WriteAllText($tmpPy, $py, [System.Text.UTF8Encoding]::new($false))
try {
    # PowerShell 5.1 cannot use `<` redirection with `&`; pipe via Get-Content.
    # ``manage.py shell`` runs in interactive mode, so trailing blank lines are
    # re-parsed by the REPL and produce spurious IndentationError noise. Use
    # ``exec(open(path).read())`` to run the body as one chunk.
    $exec = "exec(open(r'$tmpPy', encoding='utf-8').read())"
    $output = & $venvPy manage.py shell --no-startup -c $exec 2>&1
} finally {
    Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue
}
$ec = $LASTEXITCODE
$output | ForEach-Object { Write-Host "  $_" }
if ($ec -ne 0) {
    Write-Host ""
    Status "seed failed" $false
    Read-Host "Press Enter to close"
    exit 1
}
Status "seed complete" $true

# --- 3. Trigger an allocation run through the live API ------------------
Write-Host ""
Write-Host "[3/3] Allocation run via live API" -ForegroundColor Cyan

$loginBody = '{"email":"admininvigilo@gmail.com","password":"Invigilo@2026"}'
try {
    $login = Invoke-WebRequest -Uri "$apiBase/api/v1/auth/login/" -Method POST -ContentType "application/json" -Body $loginBody -UseBasicParsing -TimeoutSec 5
    $token = ($login.Content | ConvertFrom-Json).access
    Status "admin login -> 200" $true
} catch {
    Status "admin login failed" $false
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "  Skipping the allocation run; you can trigger it from the dashboard." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Seed complete (no allocation run)." -ForegroundColor Green
    Read-Host "Press Enter to close"
    exit 0
}

# Get the active period id
$h = @{ Authorization = "Bearer $token" }
try {
    $periods = Invoke-WebRequest -Uri "$apiBase/api/v1/exams/periods/?is_active=true" -Headers $h -UseBasicParsing -TimeoutSec 5
    $periodId = ($periods.Content | ConvertFrom-Json).results[0].id
    if (-not $periodId) {
        Status "no active period returned" $false
        Write-Host "  Skipping the allocation run." -ForegroundColor Yellow
        Read-Host "Press Enter to close"
        exit 0
    }
    $runBody = "{`"period_id`":`"$periodId`"}"
    $run = Invoke-WebRequest -Uri "$apiBase/api/v1/allocations/runs/" -Method POST -ContentType "application/json" -Body $runBody -Headers $h -UseBasicParsing -TimeoutSec 30
    $rj = $run.Content | ConvertFrom-Json
    Status ("allocation run -> $($run.StatusCode)  placed=$($rj.sessions_placed)/$($rj.sessions_total)") $true
} catch {
    Status "allocation run failed" $false
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "  The seed data is in place; you can run the engine from the dashboard." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  SEED COMPLETE" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Login:      http://localhost:3000/login" -ForegroundColor Cyan
Write-Host "    Email:    admininvigilo@gmail.com" -ForegroundColor Yellow
Write-Host "    Password: Invigilo@2026" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Demo accounts (password = Demo@2026<Role>):" -ForegroundColor Cyan
Write-Host "    officer1@invigilo.local    -- Examination Officer" -ForegroundColor Yellow
Write-Host "    hod.cs@invigilo.local      -- Head of Department (CS)" -ForegroundColor Yellow
Write-Host "    dean.sci@invigilo.local    -- Faculty Dean (SCI)" -ForegroundColor Yellow
Write-Host "    inv1..inv12@invigilo.local -- Invigilators" -ForegroundColor Yellow
Write-Host "    student1@invigilo.local    -- Student" -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to close"

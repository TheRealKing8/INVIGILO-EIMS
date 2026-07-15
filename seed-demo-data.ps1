# Seed extra data so the dashboard isn't completely empty.
# Run from C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System\backend
# with the .env that points at Postgres.

$ErrorActionPreference = "Stop"
$backend = "C:\Users\isaac.odhiambo\Desktop\Examination-Invigilation-Management-System\backend"
Set-Location $backend

$script = @'
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from apps.academic.models import Course, Department, Faculty, Program
from apps.allocations.models import Allocation, AllocationRun, Conflict
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room

period = ExamPeriod.objects.filter(is_active=True).first()
if not period:
    print("No active period found; aborting.")
else:
    faculty = Faculty.objects.first()
    dept_cs = Department.objects.filter(code="CS").first()
    dept_mth = Department.objects.filter(code="MTH").first()
    b_main = Building.objects.filter(code="MAIN").first()
    b_sci = Building.objects.filter(code="SCI").first()
    courses = list(Course.objects.all())
    rooms = list(Room.objects.all())

    # Invigilator profiles (3 staff, 1 of each from CS, MTH, PHY-style depts)
    admin = __import__("apps.accounts.models", fromlist=["User"]).User.objects.get(email="admininvigilo@gmail.com")
    extra_users = []
    for i, (nm, dept, cap) in enumerate([
        ("Alice Wanjiku", dept_cs, 6),
        ("Brian Kiprotich", dept_mth, 5),
        ("Carol Otieno", dept_cs, 4),
    ], start=1):
        from apps.accounts.models import User
        u, _ = User.objects.update_or_create(
            email=f"invigilator{i}.invigilo@gmail.com",
            defaults={"full_name": nm, "is_active": True, "is_email_verified": True},
        )
        u.set_password("ChangeMe123!")
        u.save()
        extra_users.append(u)
        InvigilatorProfile.objects.update_or_create(
            user=u,
            defaults={
                "primary_department": dept,
                "max_sessions_per_cycle": cap,
                "is_active": True,
                "rating": "4.5",
            },
        )

    # Exam sessions in the next 14 days
    if rooms and courses:
        base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
        for i, c in enumerate(courses):
            room = rooms[i % len(rooms)]
            start = base + timedelta(days=i, hours=2)
            ExamSession.objects.get_or_create(
                period=period,
                course=c,
                room=room,
                starts_at=start,
                defaults={
                    "ends_at": start + timedelta(hours=2),
                    "capacity": 60,
                    "registered": 45 + i,
                    "invigilators_required": 2,
                    "status": "scheduled",
                },
            )

    # Sample incident
    from apps.incidents.models import Incident
    Incident.objects.get_or_create(
        title="Late invigilator (seed)",
        defaults={
            "body": "Auto-seeded for dashboard demo.",
            "reporter": admin,
            "severity": "medium",
            "status": "open",
        },
    )

    print("Seed complete.")
    print(f"  invigilators: {InvigilatorProfile.objects.count()}")
    print(f"  sessions:     {ExamSession.objects.count()}")
    print(f"  incidents:    {Incident.objects.count()}")
'@

& ".\.venv\Scripts\python.exe" manage.py shell -c $script 2>&1
Read-Host "Press Enter to close"

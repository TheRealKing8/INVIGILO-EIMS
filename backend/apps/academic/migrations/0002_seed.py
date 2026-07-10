"""Seed reference academic data: 1 faculty, 3 departments, 4 courses.

Idempotent — uses ``get_or_create`` so it is safe to re-run on an already
populated database (handy in tests and during the MySQL→Postgres cutover).
"""
from __future__ import annotations

from django.db import migrations


def seed(apps, schema_editor):  # noqa: D401
    Faculty = apps.get_model("academic", "Faculty")
    Department = apps.get_model("academic", "Department")
    Program = apps.get_model("academic", "Program")
    Course = apps.get_model("academic", "Course")

    faculty, _ = Faculty.objects.get_or_create(
        code="SAST",
        defaults={"name": "Science, Applied Sciences & Technology"},
    )

    departments = [
        ("CS",  "Computer Science"),
        ("MTH", "Mathematics"),
        ("PHY", "Physics"),
    ]
    dept_objs = {}
    for code, name in departments:
        dept, _ = Department.objects.get_or_create(
            faculty=faculty,
            code=code,
            defaults={"name": name},
        )
        dept_objs[code] = dept

    program, _ = Program.objects.get_or_create(
        department=dept_objs["CS"],
        code="BSC-CS",
        defaults={"name": "BSc. Computer Science", "duration_years": 4},
    )

    courses = [
        ("CS101",  "Intro to Programming", 3),
        ("CS201",  "Data Structures",     3),
        ("MTH101", "Calculus I",          4),
        ("PHY101", "Mechanics",           3),
    ]
    for code, title, credits in courses:
        Course.objects.get_or_create(
            program=program,
            code=code,
            defaults={
                "title": title,
                "credit_hours": credits,
            },
        )


def noop_reverse(apps, schema_editor):  # noqa: D401
    """Seed data is intentionally not removed on reverse migration."""


class Migration(migrations.Migration):
    dependencies = [("academic", "0001_initial")]
    operations = [migrations.RunPython(seed, noop_reverse)]

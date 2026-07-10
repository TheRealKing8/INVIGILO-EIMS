"""Seed a top-of-hierarchy university + campus + a couple of course units.

Idempotent — uses ``get_or_create``. Sits on top of the existing
``0002_seed`` data so the legacy faculty, departments, programs, and
courses remain valid.
"""
from __future__ import annotations

from django.db import migrations


def seed(apps, schema_editor):  # noqa: D401
    University = apps.get_model("academic", "University")
    Campus = apps.get_model("academic", "Campus")
    Course = apps.get_model("academic", "Course")
    CourseUnit = apps.get_model("academic", "CourseUnit")

    university, _ = University.objects.get_or_create(
        code="INV",
        defaults={"name": "Invigilo State University"},
    )
    Campus.objects.get_or_create(
        university=university,
        code="MAIN",
        defaults={"name": "Main Campus", "address": "University Way"},
    )

    # Wire a small handful of course units to the existing seeded courses.
    # Year 1 / Sem 1 for everything keeps the data realistic and easy
    # to filter on in tests.
    for course_code, unit_code, unit_title in (
        ("CS101", "CS101-Y1S1", "Intro to Programming — Y1S1"),
        ("CS201", "CS201-Y2S1", "Data Structures — Y2S1"),
    ):
        try:
            course = Course.objects.get(code=course_code)
        except Course.DoesNotExist:
            continue
        CourseUnit.objects.get_or_create(
            course=course,
            code=unit_code,
            defaults={
                "title": unit_title,
                "credit_hours": course.credit_hours,
                "year": 1 if course_code == "CS101" else 2,
                "semester": 1,
            },
        )


def noop_reverse(apps, schema_editor):  # noqa: D401
    """Reference data is intentionally not removed on reverse migration."""


class Migration(migrations.Migration):
    dependencies = [("academic", "0003_academic_hierarchy")]
    operations = [migrations.RunPython(seed, noop_reverse)]

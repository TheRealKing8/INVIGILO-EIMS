"""Seed one active exam period. Sessions are seeded separately by tests
and by the demo helper; this keeps the reference data minimal.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.db import migrations


def seed(apps, schema_editor):  # noqa: D401
    ExamPeriod = apps.get_model("exams", "ExamPeriod")

    today = date.today()
    ExamPeriod.objects.get_or_create(
        code="2026-S1",
        defaults={
            "name": "Semester 1, 2026",
            "starts_on": today + timedelta(days=14),
            "ends_on": today + timedelta(days=35),
            "is_active": True,
        },
    )


def noop_reverse(apps, schema_editor):  # noqa: D401
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("exams", "0001_initial"),
        ("academic", "0002_seed"),
    ]
    operations = [migrations.RunPython(seed, noop_reverse)]

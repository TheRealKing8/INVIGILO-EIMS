"""Seed 2 buildings with 6 rooms total (capacities 30..250)."""
from __future__ import annotations

from django.db import migrations


def seed(apps, schema_editor):  # noqa: D401
    Building = apps.get_model("rooms", "Building")
    Room = apps.get_model("rooms", "Room")

    main, _ = Building.objects.get_or_create(
        code="MAIN",
        defaults={"name": "Main Academic Block", "address": "1 University Way"},
    )
    sci, _ = Building.objects.get_or_create(
        code="SCI",
        defaults={"name": "Science Complex", "address": "2 University Way"},
    )

    rooms = [
        ("LH-A1", main, 120, ["projector"]),
        ("LH-A2", main,  80, ["projector", "mic"]),
        ("LH-B1", main, 200, ["projector", "mic", "recording"]),
        ("LAB-1", sci,   40, ["computers", "projector"]),
        ("LAB-2", sci,   40, ["computers", "projector"]),
        ("LAB-3", sci,   30, ["computers"]),
    ]
    for code, bldg, cap, equipment in rooms:
        Room.objects.get_or_create(
            building=bldg,
            code=code,
            defaults={"capacity": cap, "equipment": equipment},
        )


def noop_reverse(apps, schema_editor):  # noqa: D401
    pass


class Migration(migrations.Migration):
    dependencies = [("rooms", "0001_initial")]
    operations = [migrations.RunPython(seed, noop_reverse)]

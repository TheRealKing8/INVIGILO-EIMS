"""Seed the extended RBAC roles (Module 1).

Adds three new roles (``STUDENT``, ``SECURITY_OFFICER``, ``GUEST``) and
the five permission codenames they need (``exam.session.view_own``,
``timetable.view_own``, ``timetable.public.view``,
``attendance.checkin_any``, ``incident.log_for_others``). Reconciles
the role/permission matrix idempotently — the same pattern as
``0002_seed_rbac.py``.

This is a **data** migration. The schema is unchanged; the matrix in
``apps/accounts/seed.py`` remains the source of truth and is what
later migrations should import from when extending RBAC further.
"""
from __future__ import annotations

from django.db import migrations

from apps.accounts.seed import PERMISSIONS, ROLE_PERMISSIONS, ROLES


def seed(apps, schema_editor):  # type: ignore[no-untyped-def]
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    # Upsert every role defined in the seed.
    for entry in ROLES:
        Role.objects.update_or_create(
            code=entry["code"],
            defaults={
                "name": entry["name"],
                "description": entry["description"],
                "is_active": True,
            },
        )

    # Upsert every permission defined in the seed.
    for entry in PERMISSIONS:
        Permission.objects.update_or_create(
            codename=entry["codename"],
            defaults={
                "name": entry["name"],
                "description": entry.get("description", ""),
            },
        )

    # Reconcile the role/permission matrix.
    for role_code, permission_codes in ROLE_PERMISSIONS:
        try:
            role = Role.objects.get(code=role_code)
        except Role.DoesNotExist:
            continue
        desired = set(permission_codes)
        # Remove unwanted.
        RolePermission.objects.filter(role=role).exclude(
            permission__codename__in=desired
        ).delete()
        # Add missing.
        existing = set(
            RolePermission.objects.filter(role=role).values_list(
                "permission__codename", flat=True
            )
        )
        for codename in desired - existing:
            try:
                perm = Permission.objects.get(codename=codename)
            except Permission.DoesNotExist:
                continue
            RolePermission.objects.create(role=role, permission=perm)


def unseed(apps, schema_editor):  # type: ignore[no-untyped-def]
    """Forward-compatible no-op; the data is the matrix source of truth.

    Mirrors ``0002_seed_rbac.unseed`` — we never delete seeded rows in
    reverse, so re-running the migration is safe.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_options_alter_user_managers_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

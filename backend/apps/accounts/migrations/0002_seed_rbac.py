"""Seed the RBAC tables.

Loads :mod:`apps.accounts.seed` and applies it idempotently: roles and
permissions are upserted, and the role/permission matrix is reconciled
to the seed definition. This is a **data** migration, not a schema
migration, so it can be re-run safely.
"""
from __future__ import annotations

from django.db import migrations

from apps.accounts.seed import PERMISSIONS, ROLE_PERMISSIONS, ROLES


def seed(apps, schema_editor):  # type: ignore[no-untyped-def]
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")
    RolePermission = apps.get_model("accounts", "RolePermission")

    for entry in ROLES:
        Role.objects.update_or_create(
            code=entry["code"],
            defaults={"name": entry["name"], "description": entry["description"], "is_active": True},
        )

    for entry in PERMISSIONS:
        Permission.objects.update_or_create(
            codename=entry["codename"],
            defaults={"name": entry["name"], "description": entry.get("description", "")},
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
    """Forward-compatible: leave rows in place so re-running is safe.

    We do NOT delete roles/permissions in reverse — the data is the
    authoritative source of the RBAC matrix and the migration runner
    never needs to roll it back.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

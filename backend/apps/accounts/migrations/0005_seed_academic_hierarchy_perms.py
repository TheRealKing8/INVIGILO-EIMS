"""Reconcile the RBAC matrix after adding the academic-structure
permissions (``academic.university.crud`` and ``academic.campus.crud``).

This is structurally a no-op for any database that already has the
right matrix, but it ensures existing installs pick up the new
permissions when they upgrade. The pattern is identical to
``0004_seed_extended_roles`` — same idempotent reconcile against
``apps.accounts.seed`` — and replaces the need to rewind and re-apply
that earlier migration.
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
            defaults={
                "name": entry["name"],
                "description": entry["description"],
                "is_active": True,
            },
        )

    for entry in PERMISSIONS:
        Permission.objects.update_or_create(
            codename=entry["codename"],
            defaults={
                "name": entry["name"],
                "description": entry.get("description", ""),
            },
        )

    for role_code, permission_codes in ROLE_PERMISSIONS:
        try:
            role = Role.objects.get(code=role_code)
        except Role.DoesNotExist:
            continue
        desired = set(permission_codes)
        RolePermission.objects.filter(role=role).exclude(
            permission__codename__in=desired
        ).delete()
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
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_seed_extended_roles"),
    ]

    operations = [migrations.RunPython(seed, unseed)]

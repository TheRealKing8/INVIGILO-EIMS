"""Tests for the User model — fields, helpers, and the soft-delete cycle."""
from __future__ import annotations

import pytest

from apps.accounts.models import Permission, Role, RolePermission, User, UserRole


pytestmark = pytest.mark.django_db


def _seed_minimal_rbac() -> None:
    """Create the role/permission rows that the tests reference.

    Idempotent: the rows may have been seeded by the data migration in
    apps/accounts/migrations/0002_seed_rbac.py. We use
    ``update_or_create`` so the operation is safe regardless of which
    manager is the default.
    """
    perm, _ = Permission.objects.update_or_create(
        codename="people.invigilator.crud",
        defaults={"name": "Manage invigilators"},
    )
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR",
        defaults={"name": "Invigilator", "is_active": True},
    )
    RolePermission.objects.update_or_create(role=role, permission=perm)
    return role, perm  # type: ignore[return-value]


def test_create_user_with_email_only() -> None:
    user = User.objects.create_user(email="alice@x.com", full_name="Alice")
    assert user.pk is not None
    assert user.email == "alice@x.com"
    assert user.full_name == "Alice"
    assert user.has_usable_password() is False
    assert user.is_active is True
    assert user.is_email_verified is False


def test_create_user_with_password() -> None:
    user = User.objects.create_user(
        email="bob@x.com", full_name="Bob", password="S3cur3Passw0rd!"
    )
    assert user.has_usable_password() is True
    assert user.check_password("S3cur3Passw0rd!") is True


def test_email_lookup_is_case_insensitive() -> None:
    """Emails with different cases resolve to the same user via __iexact."""
    User.objects.create_user(email="alice@x.com", full_name="Alice")
    from django.contrib.auth import get_user_model

    UserModel = get_user_model()
    assert UserModel.objects.filter(email__iexact="ALICE@x.com").exists()
    assert UserModel.objects.filter(email__iexact="alice@X.COM").exists()


def test_email_is_unique() -> None:
    User.objects.create_user(email="dup@x.com", full_name="A")
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@x.com", full_name="B")


def test_user_has_no_role_by_default() -> None:
    user = User.objects.create_user(email="solo@x.com", full_name="Solo")
    assert user.primary_role_code is None
    assert user.roles().count() == 0


def test_user_primary_role_picks_highest_precedence() -> None:
    role_inv, _ = _seed_minimal_rbac()
    role_eo, _ = Role.objects.update_or_create(
        code="EXAMINATION_OFFICER",
        defaults={"name": "EO", "is_active": True},
    )
    user = User.objects.create_user(email="multi@x.com", full_name="Multi")
    UserRole.objects.create(user=user, role=role_inv)
    UserRole.objects.create(user=user, role=role_eo)
    assert user.primary_role_code == "EXAMINATION_OFFICER"


def test_user_has_permission_via_role() -> None:
    role, perm = _seed_minimal_rbac()
    user = User.objects.create_user(email="p@x.com", full_name="P")
    UserRole.objects.create(user=user, role=role)
    assert user.has_permission("people.invigilator.crud") is True
    assert user.has_permission("people.student.crud") is False


def test_superuser_has_all_permissions() -> None:
    user = User.objects.create_superuser(
        email="root@x.com", full_name="Root", password="S3cur3Passw0rd!"
    )
    assert user.has_permission("anything.whatever") is True


def test_soft_delete_hides_from_default_manager() -> None:
    user = User.objects.create_user(email="bye@x.com", full_name="Bye")
    user.soft_delete()
    assert User.objects.filter(pk=user.pk).count() == 0
    assert User.all_objects.filter(pk=user.pk).count() == 1


def test_register_failed_login_locks_at_threshold(settings) -> None:  # type: ignore[no-untyped-def]
    settings.LOCKOUT_THRESHOLD = 3
    settings.LOCKOUT_DURATION_MINUTES = 5
    user = User.objects.create_user(email="lock@x.com", full_name="L")
    for _ in range(3):
        user.register_failed_login()
    assert user.is_locked() is True
    user.register_successful_login()
    user.refresh_from_db()
    assert user.is_locked() is False

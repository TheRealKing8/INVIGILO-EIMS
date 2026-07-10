"""Shared pytest fixtures for all app test suites.

Provides a ``verified_user`` (a confirmed user with no role), a
``client`` (DRF APIClient), and ``grant_permission`` helper to give a
user the permission codes needed for a specific test.
"""
from __future__ import annotations

from typing import Iterable

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Permission, Role, RolePermission, UserRole


User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def verified_user(db) -> User:  # type: ignore[no-untyped-def]
    """A confirmed, active user with no roles attached."""
    user = User.objects.create_user(
        email="tester@x.com",
        full_name="Tester",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    return user


@pytest.fixture
def grant_permission(db):  # type: ignore[no-untyped-def]
    """Factory fixture: returns a function that grants permission codes to a user.

    Usage::

        def test_x(client, verified_user, grant_permission):
            grant_permission(verified_user, "exam.session.crud")
            client.force_authenticate(verified_user)
            ...
    """
    role, _ = Role.objects.update_or_create(
        code="TEST_RUNTIME", defaults={"name": "Test runtime role", "is_active": True}
    )

    def _grant(user: User, *codes: str) -> None:
        for code in codes:
            perm, _ = Permission.objects.update_or_create(
                codename=code, defaults={"name": code}
            )
            RolePermission.objects.update_or_create(role=role, permission=perm)
        UserRole.objects.update_or_create(user=user, role=role)

    return _grant

"""Shared pytest fixtures for the accounts app.

The ``verified_user`` and ``invigilator_role`` fixtures are reused by
every test file in this app. Centralising them avoids the pytest-django
issue where a fixture in one ``test_*.py`` is not visible in another
``test_*.py`` in the same directory.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Role, UserRole


User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def invigilator_role() -> Role:
    # The 0002_seed_rbac migration already creates an INVIGILATOR role;
    # use update_or_create so this fixture is idempotent regardless of
    # whether the test DB started empty (and so we don't fight a
    # UNIQUE-constraint failure on the role.code index).
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    return role


@pytest.fixture
def verified_user(invigilator_role: Role):  # type: ignore[no-untyped-def]
    user = User.objects.create_user(
        email="alice@x.com",
        full_name="Alice",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=invigilator_role)
    return user


@pytest.fixture
def student_user() -> User:
    """A verified STUDENT user — used by tests that need a user
    that can complete a password-only login (no OTP step) and
    then exercise the JWT / cookie / refresh mechanics.

    Added when the OTP policy was widened to all staff roles — the
    older ``verified_user`` fixture is an INVIGILATOR and now goes
    through the OTP second step, which is the wrong shape for
    tests that only care about the cookie set / refresh rotation
    / logout mechanics.
    """
    role, _ = Role.objects.update_or_create(
        code="STUDENT", defaults={"name": "Student", "is_active": True}
    )
    user = User.objects.create_user(
        email="student@x.com",
        full_name="Student",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user

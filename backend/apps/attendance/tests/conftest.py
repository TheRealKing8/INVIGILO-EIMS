"""Local fixtures for the attendance test suite.

Adds three fixtures on top of the project-level ones:

  * ``allocation``  — a confirmed allocation tying ``verified_user``
                      to a session via an InvigilatorProfile.
  * ``security_user`` — a fresh user with the SECURITY_OFFICER role
                      (no allocations, used to test bulk check-in).
  * ``unallocated_invigilator_user`` — a second invigilator not on
                      the session's allocation list, used to verify
                      the 403 path.

The incidents ``session`` fixture provides the ExamSession; we reuse
it directly.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Role, UserRole
from apps.allocations.models import Allocation, AllocationRun
from apps.invigilators.models import InvigilatorProfile

User = get_user_model()


@pytest.fixture
def invigilator_profile(verified_user):  # type: ignore[no-untyped-def]
    """The InvigilatorProfile row that pairs with ``verified_user``."""
    profile, _ = InvigilatorProfile.objects.update_or_create(
        user=verified_user, defaults={}
    )
    return profile


@pytest.fixture
def allocation(db, verified_user, invigilator_profile, session):  # type: ignore[no-untyped-def]
    """A confirmed allocation tying ``verified_user`` to ``session``.

    Self check-in requires a confirmed allocation — the view checks
    this directly. We create one AllocationRun + one Allocation
    inside it.
    """
    run = AllocationRun.objects.create(
        period=session.period,
        triggered_by=verified_user,
        sessions_total=1,
        sessions_placed=1,
    )
    alloc = Allocation.objects.create(
        run=run,
        session=session,
        invigilator=invigilator_profile,
        role="invigilator",
        status="confirmed",
    )
    return alloc


@pytest.fixture
def security_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="SECURITY_OFFICER", defaults={"name": "Security Officer", "is_active": True}
    )
    user = User.objects.create_user(
        email="sec@x.com",
        full_name="Sec",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def unallocated_invigilator_user(db):  # type: ignore[no-untyped-def]
    """A second invigilator with no allocation on the test session."""
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    user = User.objects.create_user(
        email="bob@x.com",
        full_name="Bob",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    InvigilatorProfile.objects.update_or_create(user=user, defaults={})
    return user


@pytest.fixture
def student_user(db):  # type: ignore[no-untyped-def]
    """A STUDENT user with the attendance.checkin_own permission.

    Defined locally rather than imported from
    ``apps/accounts/tests/conftest.py`` because pytest's conftest
    discovery is path-based — a fixture in a sibling test directory
    isn't visible from here.
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


@pytest.fixture
def verified_user(db):  # type: ignore[no-untyped-def]
    """A confirmed user with the INVIGILATOR role and the seeded
    ``attendance.checkin_own`` permission.

    Mirrors ``apps/accounts/tests/conftest.verified_user``. Defined
    locally for the same path-discovery reason as ``student_user``
    above — the project-level fixture gives a bare user with no
    role, which isn't useful for the check-in tests.
    """
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    user = User.objects.create_user(
        email="alice@x.com",
        full_name="Alice",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user

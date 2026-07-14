"""Local fixtures for the notifications test suite.

Provides:
  * ``session`` — a fully-wired ExamSession (Faculty/Department/
    Program/Course/Building/Room/ExamPeriod). Mirrors the fixture in
    ``apps/incidents/tests/test_api.py``; defined locally because
    pytest's conftest discovery is path-based and that one is a test
    file rather than a conftest.
  * ``invigilator_profile`` — pairs with ``verified_user`` (INVIGILATOR).
  * ``second_invigilator_profile`` + ``second_invigilator_user`` — for
    the reassign test (we need two invigilators to swap).
  * ``allocation`` — a confirmed Allocation tying verified_user to a
    session, with the AllocationRun scaffolding.
  * ``verified_user`` — local copy of the INVIGILATOR-role user
    (the project-level fixture is a bare user with no role).
  * ``student_user`` — local copy of the STUDENT-role user (same
    reason).
  * ``officer_user`` — local copy of the EXAMINATION_OFFICER-role
    user (the incident-escalation test fires a notification at
    every EO).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Role, UserRole
from apps.academic.models import Course, Department, Faculty, Program
from apps.allocations.models import Allocation, AllocationRun
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room

User = get_user_model()


@pytest.fixture
def session(db):  # type: ignore[no-untyped-def]
    """A future-dated scheduled ExamSession. Same shape as
    ``apps/incidents/tests/test_api.py::session``."""
    f = Faculty.objects.create(code="F", name="F")
    d = Department.objects.create(faculty=f, code="D", name="D")
    p = Program.objects.create(department=d, code="P", name="P")
    course = Course.objects.create(program=p, code="C", title="C", credit_hours=3)
    building = Building.objects.create(code="B", name="B")
    room = Room.objects.create(building=building, code="R", capacity=100)
    period = ExamPeriod.objects.create(
        code="T1", name="Term 1",
        starts_on=date.today(), ends_on=date.today() + timedelta(days=30),
    )
    # Future-dated: starts in 1 day, ends +2h.
    from datetime import datetime, timedelta as _td, timezone as _tz
    start = datetime.now(_tz.utc) + _td(days=1)
    return ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at=start, ends_at=start + _td(hours=2),
        capacity=100, registered=80, invigilators_required=1, status="scheduled",
    )


@pytest.fixture
def verified_user(db):  # type: ignore[no-untyped-def]
    """INVIGILATOR-role user. The project-level fixture is bare."""
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    user = User.objects.create_user(
        email="alice@x.com",
        full_name="Alice Invigilator",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def student_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="STUDENT", defaults={"name": "Student", "is_active": True}
    )
    user = User.objects.create_user(
        email="student@x.com",
        full_name="Stu",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def officer_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="EXAMINATION_OFFICER",
        defaults={"name": "Examination Officer", "is_active": True},
    )
    user = User.objects.create_user(
        email="officer@x.com",
        full_name="Olivia Officer",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def invigilator_profile(verified_user):  # type: ignore[no-untyped-def]
    profile, _ = InvigilatorProfile.objects.update_or_create(
        user=verified_user, defaults={}
    )
    return profile


@pytest.fixture
def second_invigilator_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    user = User.objects.create_user(
        email="bob@x.com",
        full_name="Bob Invigilator",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    InvigilatorProfile.objects.update_or_create(user=user, defaults={})
    return user


@pytest.fixture
def allocation(db, verified_user, invigilator_profile, session):  # type: ignore[no-untyped-def]
    """A confirmed allocation tying ``verified_user`` to ``session``."""
    run = AllocationRun.objects.create(
        period=session.period,
        triggered_by=verified_user,
        sessions_total=1,
        sessions_placed=1,
    )
    return Allocation.objects.create(
        run=run,
        session=session,
        invigilator=invigilator_profile,
        role="invigilator",
        status="confirmed",
    )

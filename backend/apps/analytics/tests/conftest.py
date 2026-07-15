"""Local fixtures for the analytics test suite.

Mirrors the patterns established by the Phase 14 notifications and
Phase 13 attendance conftests:

* ``session``, ``period`` — an active :class:`ExamPeriod` plus a
  scheduled :class:`ExamSession`. Two future sessions so the
  "sessions_by_day" cap test can assert on day-2 contents.
* ``verified_user`` + ``invigilator_profile`` — local copy of the
  INVIGILATOR-role user (the project-level fixture is bare; see
  ``apps/attendance/tests/conftest.py`` for the path-discovery
  rationale).
* ``officer_user`` — local copy of the EXAMINATION_OFFICER-role
  user.
* ``allocation``, ``allocation_run`` — a confirmed allocation tying
  ``verified_user`` to a session.
* ``checkin`` — a check-in row for the late-vs-on-time tests.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Role, UserRole
from apps.academic.models import Course, Department, Faculty, Program
from apps.allocations.models import Allocation, AllocationRun
from apps.attendance.models import CheckIn
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room

User = get_user_model()


@pytest.fixture(autouse=True)
def _isolate_active_period(db):  # type: ignore[no-untyped-def]
    """Make sure the seeded ``2026-S1`` period doesn't interfere
    with the period asserted in each test. The seed ships with one
    active period, but the analytics test fixtures create a new
    one — without this autouse helper, two would be active and
    ``_active_period()`` would pick the seeded one, not the
    fixture's. Same pattern as ``apps/ai/tests/test_chat.py``.
    """
    ExamPeriod.objects.filter(is_active=True).update(is_active=False)
    yield
    ExamPeriod.objects.filter(is_active=True).update(is_active=False)


@pytest.fixture
def period(db):  # type: ignore[no-untyped-def]
    """An active :class:`ExamPeriod` for the next 60 days."""
    return ExamPeriod.objects.create(
        code="AN1", name="Analytics Term 1", is_active=True,
        starts_on=date.today(), ends_on=date.today() + timedelta(days=60),
    )


@pytest.fixture
def second_period(db):  # type: ignore[no-untyped-def]
    """An inactive period (used for the no-active-period test)."""
    return ExamPeriod.objects.create(
        code="AN0", name="Old Term", is_active=False,
        starts_on=date.today() - timedelta(days=200),
        ends_on=date.today() - timedelta(days=100),
    )


@pytest.fixture
def session(db, period):  # type: ignore[no-untyped-def]
    """A future-dated scheduled ExamSession inside the active period."""
    f = Faculty.objects.create(code="F", name="F")
    d = Department.objects.create(faculty=f, code="D", name="D")
    p = Program.objects.create(department=d, code="P", name="P")
    course = Course.objects.create(program=p, code="AN101", title="Analytics", credit_hours=3)
    building = Building.objects.create(code="B", name="B")
    room = Room.objects.create(building=building, code="R", capacity=100)
    start = datetime.now(dt_timezone.utc) + timedelta(days=1)
    return ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at=start, ends_at=start + timedelta(hours=2),
        capacity=100, registered=80, invigilators_required=2, status="scheduled",
    )


@pytest.fixture
def second_session(db, period, session):  # type: ignore[no-untyped-def]
    """A second session on the same day as ``session`` (day-1 of the
    ``sessions_by_day`` output)."""
    f = session.course.program.department.faculty
    d = session.course.program.department
    p = session.course.program
    course2 = Course.objects.create(program=p, code="AN102", title="Analytics 2", credit_hours=3)
    building = session.room.building
    room2 = Room.objects.create(building=building, code="R2", capacity=100)
    start = session.starts_at + timedelta(hours=3)
    return ExamSession.objects.create(
        period=period, course=course2, room=room2,
        starts_at=start, ends_at=start + timedelta(hours=2),
        capacity=100, registered=80, invigilators_required=2, status="scheduled",
    )


@pytest.fixture
def far_session(db, period):  # type: ignore[no-untyped-def]
    """A session beyond the 7-day window — used to assert the
    ``sessions_by_day`` cap excludes it."""
    f = Faculty.objects.create(code="FF", name="FF")
    d = Department.objects.create(faculty=f, code="DD", name="DD")
    p = Program.objects.create(department=d, code="PP", name="PP")
    course = Course.objects.create(program=p, code="AN201", title="Far", credit_hours=3)
    building = Building.objects.create(code="BB", name="BB")
    room = Room.objects.create(building=building, code="RR", capacity=100)
    start = datetime.now(dt_timezone.utc) + timedelta(days=10)
    return ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at=start, ends_at=start + timedelta(hours=2),
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
def invigilator_profile(verified_user):  # type: ignore[no-untyped-def]
    profile, _ = InvigilatorProfile.objects.update_or_create(
        user=verified_user, defaults={"max_sessions_per_cycle": 12}
    )
    return profile


@pytest.fixture
def second_invigilator_user(db):  # type: ignore[no-untyped-def]
    """A second invigilator — used so the workload list has more
    than one row for the officer sees-all test."""
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
    profile, _ = InvigilatorProfile.objects.update_or_create(
        user=user, defaults={"max_sessions_per_cycle": 10}
    )
    return user


@pytest.fixture
def third_invigilator_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    user = User.objects.create_user(
        email="carol@x.com",
        full_name="Carol",
        password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    InvigilatorProfile.objects.update_or_create(
        user=user, defaults={"max_sessions_per_cycle": 8}
    )
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
def allocation_run(db, period, officer_user):  # type: ignore[no-untyped-def]
    """A finished AllocationRun with non-zero coverage so the
    ``coverage`` field is not None."""
    return AllocationRun.objects.create(
        period=period,
        triggered_by=officer_user,
        sessions_total=3,
        sessions_placed=3,
        capacity_utilisation="0.92",
        runtime_seconds=4,
        finished_at=datetime.now(dt_timezone.utc),
    )


@pytest.fixture
def allocation(db, allocation_run, session, verified_user, invigilator_profile):  # type: ignore[no-untyped-def]
    return Allocation.objects.create(
        run=allocation_run,
        session=session,
        invigilator=invigilator_profile,
        role="invigilator",
        status="confirmed",
    )


@pytest.fixture
def checkin(db, verified_user, session):  # type: ignore[no-untyped-def]
    """A single on-time check-in (created in the last minute)."""
    return CheckIn.objects.create(
        session=session,
        user=verified_user,
        kind="invigilator",
        method="self",
        recorded_by=verified_user,
        late=False,
    )

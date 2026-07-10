"""Tests for the allocation engine.

The engine is exercised end-to-end: we build a small fixture
(3 sessions, 4 invigilators from 2 departments, 2 rooms), run the
engine, and assert that the constraints are honoured.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.allocations.models import Allocation, AllocationRun, Conflict
from apps.allocations.services import run_engine
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room


User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def world(db):  # type: ignore[no-untyped-def]
    """3 sessions / 4 invigilators / 2 departments / 2 rooms."""
    f = Faculty.objects.create(code="ENG-F", name="Eng Test Faculty")
    d_cs = Department.objects.create(faculty=f, code="ENG-CS", name="Computer Science")
    d_math = Department.objects.create(faculty=f, code="ENG-MTH", name="Mathematics")
    p = Program.objects.create(department=d_cs, code="P", name="P")
    course = Course.objects.create(program=p, code="C101", title="Course 101", credit_hours=3)
    building = Building.objects.create(code="B", name="Block")
    r_small = Room.objects.create(building=building, code="R-S", capacity=50)
    r_big = Room.objects.create(building=building, code="R-B", capacity=200)

    period = ExamPeriod.objects.create(
        code="ENGINE-1", name="Engine Test", is_active=True,
        starts_on=date.today(), ends_on=date.today() + timedelta(days=30),
    )

    # 3 sessions on different days so overlap isn't a factor by default.
    sessions = []
    for i, (cap, room) in enumerate([(50, r_small), (200, r_big), (50, r_small)]):
        start = datetime(2026, 8, 1 + i, 9, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=2)
        sessions.append(
            ExamSession.objects.create(
                period=period, course=course, room=room,
                starts_at=start, ends_at=end,
                capacity=cap, registered=cap // 2,
                invigilators_required=2, status="scheduled",
            )
        )

    # 4 invigilators: 2 from CS, 2 from Math.
    inv = []
    for i, dept in enumerate([d_cs, d_cs, d_math, d_math]):
        u = User.objects.create_user(email=f"i{i}@x.com", full_name=f"Inv {i}")
        inv.append(InvigilatorProfile.objects.create(
            user=u, primary_department=dept, max_sessions_per_cycle=4,
        ))

    return {"period": period, "sessions": sessions, "invigilators": inv}


def test_engine_creates_a_run_and_allocations(world) -> None:  # type: ignore[no-untyped-def]
    run = run_engine(world["period"])
    assert AllocationRun.objects.count() == 1
    assert run.sessions_placed == 3
    # 3 sessions × 2 required = 6 allocation rows, all draft.
    assert Allocation.objects.filter(run=run).count() == 6
    assert Allocation.objects.filter(run=run, status="draft").count() == 6


def test_engine_honours_department_mixing(world) -> None:  # type: ignore[no-untyped-def]
    run = run_engine(world["period"])
    # Each session should have invigilators from at least 2 different departments.
    for sess in world["sessions"]:
        allocs = Allocation.objects.filter(run=run, session=sess).select_related(
            "invigilator__primary_department"
        )
        depts = {a.invigilator.primary_department_id for a in allocs}
        assert len(depts) == 2, f"Session {sess.id} has {len(depts)} dept(s), expected 2"


def test_engine_honours_workload_cap(world) -> None:  # type: ignore[no-untyped-def]
    run = run_engine(world["period"])
    # Each invigilator has max_sessions_per_cycle=4. 3 sessions × 2 slots = 6 slots.
    # With 4 invigilators and dept-mixing, the spread should be 1-2 per person.
    for inv in world["invigilators"]:
        count = Allocation.objects.filter(run=run, invigilator=inv).count()
        assert count <= inv.max_sessions_per_cycle


def test_engine_records_conflict_when_under_staffed(world) -> None:  # type: ignore[no-untyped-def]
    # Drop the invigilator count to 1, so the second pass can't fix dept-mix either.
    InvigilatorProfile.objects.exclude(pk=world["invigilators"][0].pk).delete()
    run = run_engine(world["period"])
    # At least one session should record a conflict.
    assert Conflict.objects.filter(run=run).exists()
    # And at least one session is unplaced.
    assert run.sessions_placed < run.sessions_total


def test_engine_endpoint_runs(client: APIClient, world, verified_user, grant_permission) -> None:  # type: ignore[no-untyped-def]
    grant_permission(verified_user, "allocator.run")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("allocations:allocation-run-list"),
        {"period_id": str(world["period"].id)},
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["sessions_placed"] == 3
    assert body["sessions_total"] == 6

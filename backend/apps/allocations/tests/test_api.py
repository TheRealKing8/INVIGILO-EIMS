"""Tests for the allocations read-only endpoints (engine is built in Phase 3)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.allocations.models import Allocation, AllocationRun
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room


User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def seed(db):  # type: ignore[no-untyped-def]
    """A minimal period + 2 sessions + 2 rooms + 2 invigilators + 1 run + 2 allocations."""
    f = Faculty.objects.create(code="F", name="F")
    d = Department.objects.create(faculty=f, code="D", name="D")
    p = Program.objects.create(department=d, code="P", name="P")
    course = Course.objects.create(program=p, code="C", title="C", credit_hours=3)
    building = Building.objects.create(code="B", name="B")
    room1 = Room.objects.create(building=building, code="R1", capacity=100)
    room2 = Room.objects.create(building=building, code="R2", capacity=50)
    period = ExamPeriod.objects.create(
        code="T1", name="Term 1",
        starts_on=date.today(), ends_on=date.today() + timedelta(days=30),
    )
    s1 = ExamSession.objects.create(
        period=period, course=course, room=room1,
        starts_at="2026-08-01T09:00:00Z", ends_at="2026-08-01T11:00:00Z",
        capacity=100, registered=80, invigilators_required=2, status="scheduled",
    )
    s2 = ExamSession.objects.create(
        period=period, course=course, room=room2,
        starts_at="2026-08-02T09:00:00Z", ends_at="2026-08-02T11:00:00Z",
        capacity=50, registered=40, invigilators_required=1, status="scheduled",
    )

    inv1 = InvigilatorProfile.objects.create(
        user=User.objects.create_user(email="i1@x.com", full_name="I1"),
        primary_department=d,
    )
    inv2 = InvigilatorProfile.objects.create(
        user=User.objects.create_user(email="i2@x.com", full_name="I2"),
        primary_department=d,
    )

    run = AllocationRun.objects.create(period=period, sessions_total=2, sessions_placed=2)
    Allocation.objects.create(run=run, session=s1, invigilator=inv1, room=room1, status="draft")
    Allocation.objects.create(run=run, session=s1, invigilator=inv2, room=room1, status="draft")
    Allocation.objects.create(run=run, session=s2, invigilator=inv1, room=room2, status="draft")
    return {"period": period, "sessions": [s1, s2], "run": run}


def test_allocation_list_paginated(
    client: APIClient, verified_user, grant_permission, seed
) -> None:
    grant_permission(verified_user, "allocator.run")
    client.force_authenticate(verified_user)
    response = client.get(reverse("allocations:allocation-list"))
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert len(body["results"]) == 3


def test_allocation_filter_by_status(
    client: APIClient, verified_user, grant_permission, seed
) -> None:
    grant_permission(verified_user, "allocator.run")
    client.force_authenticate(verified_user)
    response = client.get(reverse("allocations:allocation-list"), {"status": "draft"})
    assert response.status_code == 200
    assert response.json()["count"] == 3


def test_allocation_run_listed(
    client: APIClient, verified_user, grant_permission, seed
) -> None:
    grant_permission(verified_user, "allocator.run")
    client.force_authenticate(verified_user)
    response = client.get(reverse("allocations:allocation-run-list"))
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["sessions_total"] == 2


def test_rbac_blocks_403(
    client: APIClient, verified_user, seed
) -> None:
    client.force_authenticate(verified_user)
    assert client.get(reverse("allocations:allocation-list")).status_code == 403
    assert client.get(reverse("allocations:allocation-run-list")).status_code == 403
    assert client.get(reverse("allocations:conflict-list")).status_code == 403

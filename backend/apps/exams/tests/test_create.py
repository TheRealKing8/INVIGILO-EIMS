"""Tests for the split exam.session permissions and the invigilator
self-allocate path.

Covers:
* An invigilator (with `exam.session.create` only) can `POST /sessions/`.
* A user with no permission at all is denied with 403.
* A user with only `exam.session.create` CANNOT cancel/destroy/update
  someone else's session — the lifecycle permissions stay gated on
  `exam.session.crud`.
* A successful invigilator self-create auto-creates an Allocation row
  pointing at their InvigilatorProfile.
* A user with `exam.session.crud` (admin/officer) can still create —
  the original behaviour is preserved.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.allocations.models import Allocation
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room


pytestmark = pytest.mark.django_db


@pytest.fixture
def course(db) -> Course:  # type: ignore[no-untyped-def]
    f = Faculty.objects.create(code="F", name="Faculty")
    d = Department.objects.create(faculty=f, code="D", name="Dept")
    p = Program.objects.create(department=d, code="P", name="Prog")
    return Course.objects.create(program=p, code="C101", title="Course 101", credit_hours=3)


@pytest.fixture
def room(db) -> Room:  # type: ignore[no-untyped-def]
    b = Building.objects.create(code="B", name="Block")
    return Room.objects.create(building=b, code="R", capacity=100)


@pytest.fixture
def period(db):  # type: ignore[no-untyped-def]
    from apps.exams.models import ExamPeriod
    return ExamPeriod.objects.create(
        code="P10", name="Phase 10 Period", is_active=True,
        starts_on=date.today(), ends_on=date.today() + timedelta(days=30),
    )


@pytest.fixture
def invigilator_profile(verified_user):  # type: ignore[no-untyped-def]
    return InvigilatorProfile.objects.create(
        user=verified_user,
        max_sessions_per_cycle=4,
    )


def _create_payload(course, room, period):  # type: ignore[no-untyped-def]
    return {
        "period": str(period.id),
        "course": course.id,
        "room": room.id,
        "starts_at": "2026-10-01T09:00:00Z",
        "ends_at": "2026-10-01T11:00:00Z",
        "capacity": 100,
        "registered": 0,
        "invigilators_required": 1,
    }


def test_invigilator_with_create_only_can_post_session(
    client: APIClient, verified_user, grant_permission,
    course, room, period, invigilator_profile,
) -> None:
    grant_permission(verified_user, "exam.session.create")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-list"),
        _create_payload(course, room, period),
        format="json",
    )
    assert response.status_code == 201, response.json()


def test_user_with_no_perm_cannot_post_session(
    client: APIClient, verified_user, course, room, period
) -> None:
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-list"),
        _create_payload(course, room, period),
        format="json",
    )
    assert response.status_code == 403


def test_user_with_create_only_cannot_cancel(
    client: APIClient, verified_user, grant_permission,
    course, room, period, invigilator_profile,
) -> None:
    grant_permission(verified_user, "exam.session.create")
    client.force_authenticate(verified_user)
    create = client.post(
        reverse("exams:exam-session-list"),
        _create_payload(course, room, period),
        format="json",
    )
    assert create.status_code == 201
    session_id = create.json()["id"]
    response = client.post(reverse("exams:exam-session-cancel", args=[session_id]))
    assert response.status_code == 403


def test_invigilator_create_auto_allocates(
    client: APIClient, verified_user, grant_permission,
    course, room, period, invigilator_profile,
) -> None:
    grant_permission(verified_user, "exam.session.create")
    client.force_authenticate(verified_user)
    create = client.post(
        reverse("exams:exam-session-list"),
        _create_payload(course, room, period),
        format="json",
    )
    assert create.status_code == 201
    session_id = create.json()["id"]
    # An Allocation was auto-created for the calling invigilator.
    alloc = Allocation.objects.get(
        session_id=session_id, invigilator=invigilator_profile
    )
    assert alloc.role == "chief"
    assert alloc.status == "confirmed"


def test_admin_with_crud_can_post_without_auto_allocating(
    client: APIClient, verified_user, grant_permission,
    course, room, period,
) -> None:
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    create = client.post(
        reverse("exams:exam-session-list"),
        _create_payload(course, room, period),
        format="json",
    )
    assert create.status_code == 201
    # No invigilator profile is associated with the calling user, so
    # no Allocation row is created on the admin path.
    assert Allocation.objects.filter(session_id=create.json()["id"]).count() == 0


def test_view_only_user_cannot_post_session(
    client: APIClient, verified_user, grant_permission,
    course, room, period,
) -> None:
    grant_permission(verified_user, "exam.session.view")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-list"),
        _create_payload(course, room, period),
        format="json",
    )
    # Read-only permission must not be enough to write.
    assert response.status_code == 403


def test_user_with_view_can_list_sessions(
    client: APIClient, verified_user, grant_permission, period, course, room
) -> None:
    from apps.exams.models import ExamSession
    ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at=datetime.fromisoformat("2026-10-02T09:00:00+00:00"),
        ends_at=datetime.fromisoformat("2026-10-02T11:00:00+00:00"),
        capacity=100, registered=0, status="scheduled",
    )
    grant_permission(verified_user, "exam.session.view")
    client.force_authenticate(verified_user)
    response = client.get(reverse("exams:exam-session-list"))
    assert response.status_code == 200
    assert response.json()["count"] == 1

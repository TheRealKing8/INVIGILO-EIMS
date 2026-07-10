"""Tests for the exam periods and exam sessions endpoints."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
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


def test_period_round_trip(client: APIClient, verified_user, grant_permission) -> None:
    grant_permission(verified_user, "exam.period.crud")
    client.force_authenticate(verified_user)
    today = date.today()
    response = client.post(
        reverse("exams:exam-period-list"),
        {
            "code": "2026-S2",
            "name": "Semester 2 2026",
            "starts_on": (today + timedelta(days=1)).isoformat(),
            "ends_on": (today + timedelta(days=30)).isoformat(),
            "is_active": True,
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    pid = response.json()["id"]

    detail = client.get(reverse("exams:exam-period-detail", args=[pid]))
    assert detail.json()["code"] == "2026-S2"


def test_activate_deactivates_others(
    client: APIClient, verified_user, grant_permission
) -> None:
    grant_permission(verified_user, "exam.period.crud")
    client.force_authenticate(verified_user)
    today = date.today()
    p1 = client.post(
        reverse("exams:exam-period-list"),
        {
            "code": "ACTP1",
            "name": "P1",
            "starts_on": today.isoformat(),
            "ends_on": (today + timedelta(days=7)).isoformat(),
            "is_active": True,
        },
        format="json",
    ).json()
    p2 = client.post(
        reverse("exams:exam-period-list"),
        {
            "code": "ACTP2",
            "name": "P2",
            "starts_on": (today + timedelta(days=10)).isoformat(),
            "ends_on": (today + timedelta(days=20)).isoformat(),
            "is_active": True,
        },
        format="json",
    ).json()

    response = client.post(reverse("exams:exam-period-activate", args=[p2["id"]]))
    assert response.status_code == 200
    assert response.json()["is_active"] is True

    # p1 is now soft-deactivated (is_active=False), so it is hidden by the
    # default queryset. Confirm via all_objects to bypass the soft-delete
    # filter.
    from apps.exams.models import ExamPeriod
    p1_now = ExamPeriod.all_objects.get(pk=p1["id"])
    assert p1_now.is_active is False
    p2_now = ExamPeriod.all_objects.get(pk=p2["id"])
    assert p2_now.is_active is True


def test_session_create_requires_period(
    client: APIClient, verified_user, grant_permission, course, room
) -> None:
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-list"),
        {
            "course": course.id,
            "room": room.id,
            "starts_at": "2026-08-01T09:00:00Z",
            "ends_at": "2026-08-01T11:00:00Z",
            "capacity": 100,
            "registered": 0,
            "invigilators_required": 2,
        },
        format="json",
    )
    assert response.status_code == 400
    assert "period" in response.json()


def test_session_filtered_by_status(
    client: APIClient, verified_user, grant_permission, course, room
) -> None:
    from apps.exams.models import ExamPeriod

    grant_permission(verified_user, "exam.period.crud", "exam.session.crud")
    client.force_authenticate(verified_user)
    period = ExamPeriod.objects.create(
        code="EXAM-T1", name="Term 1", is_active=True,
        starts_on=date.today(), ends_on=date.today() + timedelta(days=30),
    )
    create_resp = client.post(
        reverse("exams:exam-session-list"),
        {
            "period": str(period.id),
            "course": course.id,
            "room": room.id,
            "starts_at": "2026-08-01T09:00:00Z",
            "ends_at": "2026-08-01T12:00:00Z",
            "capacity": 100,
            "registered": 0,
            "invigilators_required": 1,
            "status": "scheduled",
        },
        format="json",
    )
    assert create_resp.status_code == 201, create_resp.json()
    response = client.get(
        reverse("exams:exam-session-list"),
        {"status": "scheduled", "period": period.id},
    )
    assert response.status_code == 200, response.json()
    assert response.json()["count"] == 1


# ---------------------------------------------------------------------------
# Module 3 — Lifecycle actions + new fields
# ---------------------------------------------------------------------------


@pytest.fixture
def period(db) -> "apps.exams.models.ExamPeriod":
    from apps.exams.models import ExamPeriod
    return ExamPeriod.objects.create(
        code="M3-P1", name="M3 Period", is_active=True,
        starts_on=date.today(), ends_on=date.today() + timedelta(days=30),
    )


@pytest.fixture
def scheduled_session(period, course, room) -> "apps.exams.models.ExamSession":
    from apps.exams.models import ExamSession
    return ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at=datetime.fromisoformat("2026-08-01T09:00:00+00:00"),
        ends_at=datetime.fromisoformat("2026-08-01T11:00:00+00:00"),
        capacity=100, registered=0, status="scheduled",
    )


def test_cancel_scheduled_session(
    client: APIClient, verified_user, grant_permission, scheduled_session
) -> None:
    from django.utils.dateparse import parse_datetime
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-cancel", args=[scheduled_session.id])
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_completed_session_is_rejected(
    client: APIClient, verified_user, grant_permission, scheduled_session
) -> None:
    scheduled_session.status = "completed"
    scheduled_session.save()
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-cancel", args=[scheduled_session.id])
    )
    assert response.status_code == 409


def test_draft_then_publish_round_trip(
    client: APIClient, verified_user, grant_permission, scheduled_session
) -> None:
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    draft = client.post(
        reverse("exams:exam-session-draft", args=[scheduled_session.id])
    )
    assert draft.status_code == 200
    assert draft.json()["status"] == "draft"
    publish = client.post(
        reverse("exams:exam-session-publish", args=[scheduled_session.id])
    )
    assert publish.status_code == 200
    assert publish.json()["status"] == "scheduled"


def test_reschedule_updates_times(
    client: APIClient, verified_user, grant_permission, scheduled_session
) -> None:
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-reschedule", args=[scheduled_session.id]),
        {
            "starts_at": "2026-08-02T10:00:00Z",
            "ends_at": "2026-08-02T12:30:00Z",
        },
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["starts_at"].startswith("2026-08-02T10:00:00")
    assert body["ends_at"].startswith("2026-08-02T12:30:00")
    assert body["duration_minutes"] == 150


def test_reschedule_rejects_invalid_range(
    client: APIClient, verified_user, grant_permission, scheduled_session
) -> None:
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-reschedule", args=[scheduled_session.id]),
        {
            "starts_at": "2026-08-02T10:00:00Z",
            "ends_at": "2026-08-02T10:00:00Z",  # equal to start
        },
        format="json",
    )
    assert response.status_code == 400


def test_reschedule_cancelled_session_is_rejected(
    client: APIClient, verified_user, grant_permission, scheduled_session
) -> None:
    scheduled_session.status = "cancelled"
    scheduled_session.save()
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-reschedule", args=[scheduled_session.id]),
        {
            "starts_at": "2026-08-02T10:00:00Z",
            "ends_at": "2026-08-02T12:00:00Z",
        },
        format="json",
    )
    assert response.status_code == 409


def test_session_serializes_hierarchy_codes(
    client: APIClient, verified_user, grant_permission, scheduled_session
) -> None:
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    response = client.get(
        reverse("exams:exam-session-detail", args=[scheduled_session.id])
    )
    assert response.status_code == 200
    body = response.json()
    assert body["course_code"] == "C101"
    assert body["course_title"] == "Course 101"
    assert body["faculty_code"] == "F"
    assert body["department_code"] == "D"
    assert body["program_code"] == "P"
    assert body["duration_minutes"] == 120


def test_session_special_requirements_round_trip(
    client: APIClient, verified_user, grant_permission, period, course, room
) -> None:
    grant_permission(verified_user, "exam.session.crud")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("exams:exam-session-list"),
        {
            "period": str(period.id),
            "course": course.id,
            "room": room.id,
            "starts_at": "2026-09-01T09:00:00Z",
            "ends_at": "2026-09-01T11:00:00Z",
            "capacity": 100,
            "special_requirements": "Large-print papers; extra time (30 min).",
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    sid = response.json()["id"]
    detail = client.get(reverse("exams:exam-session-detail", args=[sid]))
    assert "Large-print" in detail.json()["special_requirements"]

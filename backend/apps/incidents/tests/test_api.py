"""Tests for the incidents endpoints."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.exams.models import ExamPeriod, ExamSession
from apps.rooms.models import Building, Room


pytestmark = pytest.mark.django_db


@pytest.fixture
def session(db):  # type: ignore[no-untyped-def]
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
    return ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at="2026-08-01T09:00:00Z", ends_at="2026-08-01T11:00:00Z",
        capacity=100, registered=80, invigilators_required=1, status="scheduled",
    )


def test_unauthenticated_returns_401(client: APIClient) -> None:
    assert client.get(reverse("incidents:incident-list")).status_code == 401


def test_invigilator_creates_incident(
    client: APIClient, verified_user, grant_permission, session
) -> None:
    grant_permission(verified_user, "incident.create", "incident.view")
    client.force_authenticate(verified_user)
    response = client.post(
        reverse("incidents:incident-list"),
        {
            "title": "Late arrival",
            "body": "Student arrived 30 minutes late",
            "session": session.id,
            "severity": "low",
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["reporter_email"] == verified_user.email
    assert body["status"] == "open"


def test_status_transition_requires_update_status_permission(
    client: APIClient, verified_user, grant_permission, session
) -> None:
    grant_permission(verified_user, "incident.create", "incident.view")
    client.force_authenticate(verified_user)
    create = client.post(
        reverse("incidents:incident-list"),
        {"title": "X", "session": session.id, "severity": "medium"},
        format="json",
    ).json()
    # No incident.update_status -> 403.
    response = client.patch(
        reverse("incidents:incident-set-status", args=[create["id"]]),
        {"status": "investigating"},
        format="json",
    )
    assert response.status_code == 403


def test_officer_can_update_status(
    client: APIClient, verified_user, grant_permission, session
) -> None:
    grant_permission(
        verified_user, "incident.create", "incident.view", "incident.update_status"
    )
    client.force_authenticate(verified_user)
    create = client.post(
        reverse("incidents:incident-list"),
        {"title": "X", "session": session.id, "severity": "medium"},
        format="json",
    ).json()
    response = client.patch(
        reverse("incidents:incident-set-status", args=[create["id"]]),
        {"status": "investigating"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "investigating"


def test_filter_by_severity(
    client: APIClient, verified_user, grant_permission, session
) -> None:
    grant_permission(verified_user, "incident.create", "incident.view")
    client.force_authenticate(verified_user)
    for sev in ("low", "low", "high"):
        client.post(
            reverse("incidents:incident-list"),
            {"title": f"X {sev}", "session": session.id, "severity": sev},
            format="json",
        )
    response = client.get(reverse("incidents:incident-list"), {"severity": "low"})
    assert response.status_code == 200
    assert response.json()["count"] == 2

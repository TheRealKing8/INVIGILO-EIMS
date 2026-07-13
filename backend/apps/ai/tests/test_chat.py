"""Tests for the AI assistant endpoint.

The assistant is rule-based and fed live DB data. We verify:

* the endpoint requires auth;
* a `status` question returns the active period's name;
* a `conflicts` question enumerates the Conflict rows that exist;
* an empty message is rejected with 400;
* a long message (> 500 chars) is rejected with 400.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.allocations.models import AllocationRun, Conflict
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room


User = get_user_model()
pytestmark = pytest.mark.django_db


def test_chat_requires_auth(client: APIClient) -> None:
    response = client.post(reverse("ai:ai-chat"), {"message": "status"}, format="json")
    assert response.status_code in (401, 403)


def test_chat_rejects_empty_message(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": ""}, format="json")
    assert response.status_code == 400
    assert "message" in response.json()["detail"]


def test_chat_rejects_overlong_message(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "x" * 501}, format="json")
    assert response.status_code == 400


def test_chat_status_reports_active_period(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    # The base seed installs a default active period; this test cares
    # only about the one it creates, so deactivate any existing ones.
    ExamPeriod.objects.filter(is_active=True).update(is_active=False)
    ExamPeriod.objects.create(
        code="AI-1", name="AI Test Cycle", is_active=True,
        starts_on=date.today(), ends_on=date.today() + timedelta(days=14),
    )
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "status"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert "AI-1" in body["reply"]
    assert body["intent"] == "status"
    assert isinstance(body["suggestions"], list)
    assert body["context"]["active_period"] == "AI-1"


def test_chat_help_when_no_period(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    # No active period — deactivate all (the base seed has one).
    ExamPeriod.objects.filter(is_active=True).update(is_active=False)
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "what's the status"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert "no active exam period" in body["reply"].lower()
    assert body["context"]["active_period"] is None


def test_chat_conflicts_lists_open_conflicts(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    f = Faculty.objects.create(code="AI-F", name="AI Faculty")
    d = Department.objects.create(faculty=f, code="AI-D", name="D")
    p = Program.objects.create(department=d, code="AI-P", name="P")
    course = Course.objects.create(program=p, code="AIC-101", title="X", credit_hours=3)
    building = Building.objects.create(code="AI-B", name="B")
    room = Room.objects.create(building=building, code="AI-R", capacity=50)
    period = ExamPeriod.objects.create(
        code="AI-C", name="Conflicts Cycle", is_active=True,
        starts_on=date.today(), ends_on=date.today() + timedelta(days=10),
    )
    session = ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc),
        capacity=50, registered=20, invigilators_required=2, status="scheduled",
    )
    run = AllocationRun.objects.create(
        period=period, sessions_total=1, sessions_placed=1,
        avg_workload=1, max_workload=1, capacity_utilisation=1, runtime_seconds=1,
    )
    Conflict.objects.create(
        run=run, type="workload_cap", severity="error",
        detail="Example detail", session=session,
    )

    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "what conflicts do we have"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "conflicts"
    assert "workload cap" in body["reply"]
    assert body["context"]["open_conflict_count"] == 1


def test_chat_invigilators_reports_total(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    f = Faculty.objects.create(code="AI-IF", name="F")
    d = Department.objects.create(faculty=f, code="AI-ID", name="D")
    for i in range(3):
        u = User.objects.create_user(email=f"ai-inv-{i}@x.com", full_name=f"Inv {i}")
        InvigilatorProfile.objects.create(user=u, primary_department=d, max_sessions_per_cycle=4)

    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "how many invigilators do we have"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "invigilators"
    assert "3" in body["reply"]
    assert body["context"]["invigilator_total"] == 3


def test_chat_intent_help_on_unknown(client: APIClient, verified_user) -> None:  # type: ignore[no-untyped-def]
    client.force_authenticate(verified_user)
    response = client.post(reverse("ai:ai-chat"), {"message": "hello there"}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "help"

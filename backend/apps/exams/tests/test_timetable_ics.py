"""Tests for the timetable ``.ics`` download endpoint (Phase 18).

Two tests:

  1. Authenticated request returns a valid VCALENDAR with one
     VEVENT per matching session and the right content type /
     filename headers.
  2. Unauthenticated request returns 401.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.exams.models import ExamPeriod, ExamSession
from apps.rooms.models import Building, Room

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def exam_period(db):  # type: ignore[no-untyped-def]
    return ExamPeriod.objects.create(
        code="P1", name="Period 1", starts_on="2026-01-01", ends_on="2030-12-31"
    )


@pytest.fixture
def course(db):  # type: ignore[no-untyped-def]
    f = Faculty.objects.create(code="F", name="F")
    d = Department.objects.create(faculty=f, code="D", name="D")
    p = Program.objects.create(department=d, code="P", name="P")
    return Course.objects.create(
        program=p, code="TT101", title="Timetable Test", credit_hours=3
    )


@pytest.fixture
def building(db):  # type: ignore[no-untyped-def]
    return Building.objects.create(code="TB", name="Test Building")


@pytest.fixture
def in_week_session(course, exam_period, building):  # type: ignore[no-untyped-def]
    """A session in 2 days — falls inside the default ``?range=week``."""
    room = Room.objects.create(building=building, code="TR1", capacity=100)
    starts = timezone.now() + timedelta(days=2)
    ends = starts + timedelta(hours=2)
    return ExamSession.objects.create(
        period=exam_period, course=course, room=room,
        starts_at=starts, ends_at=ends,
        capacity=100, registered=80, invigilators_required=1, status="scheduled",
    )


@pytest.fixture
def another_in_week_session(course, exam_period, building):  # type: ignore[no-untyped-def]
    """A second session in 4 days — also inside the default week window."""
    room = Room.objects.create(building=building, code="TR2", capacity=100)
    starts = timezone.now() + timedelta(days=4)
    ends = starts + timedelta(hours=2)
    return ExamSession.objects.create(
        period=exam_period, course=course, room=room,
        starts_at=starts, ends_at=ends,
        capacity=100, registered=40, invigilators_required=2, status="scheduled",
    )


@pytest.fixture
def out_of_week_session(course, exam_period, building):  # type: ignore[no-untyped-def]
    """A session 30 days out — outside the default week window but
    inside the ``?range=all`` window."""
    room = Room.objects.create(building=building, code="TR3", capacity=100)
    starts = timezone.now() + timedelta(days=30)
    ends = starts + timedelta(hours=2)
    return ExamSession.objects.create(
        period=exam_period, course=course, room=room,
        starts_at=starts, ends_at=ends,
        capacity=100, registered=10, invigilators_required=1, status="scheduled",
    )


@pytest.fixture
def cancelled_in_week_session(course, exam_period, building):  # type: ignore[no-untyped-def]
    """A cancelled session inside the week window — must be excluded."""
    room = Room.objects.create(building=building, code="TR4", capacity=100)
    starts = timezone.now() + timedelta(days=3)
    ends = starts + timedelta(hours=1)
    return ExamSession.objects.create(
        period=exam_period, course=course, room=room,
        starts_at=starts, ends_at=ends,
        capacity=100, registered=0, invigilators_required=1, status="cancelled",
    )


@pytest.fixture
def anon_user(db):  # type: ignore[no-untyped-def]
    """An authenticated user with no role — IsAuthenticated true, but
    no codename to gate on. Lets the test hit the endpoint without
    going through the OTP second step.
    """
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        email="anon@x.com", full_name="Anon", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )


# ---------------------------------------------------------------------------
# 1) Authenticated request returns a valid VCALENDAR
# ---------------------------------------------------------------------------
def test_timetable_ics_returns_valid_calendar(
    client: APIClient,
    anon_user,  # noqa: ARG001
    in_week_session,  # noqa: ARG001
    another_in_week_session,  # noqa: ARG001
    out_of_week_session,  # noqa: ARG001
    cancelled_in_week_session,  # noqa: ARG001
) -> None:
    client.force_authenticate(anon_user)

    # Default range = week. Both in-week sessions are in range; the
    # out-of-week and cancelled ones are not.
    response = client.get("/api/v1/exams/timetable.ics")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/calendar")
    assert response["Content-Disposition"] == 'attachment; filename="invigilo-timetable.ics"'

    body = response.content.decode("utf-8")
    # VCALENDAR envelope.
    assert body.startswith("BEGIN:VCALENDAR\r\n")
    assert body.rstrip("\r\n").endswith("END:VCALENDAR")
    # CRLF line endings (RFC 5545 mandates this).
    assert "\r\n" in body
    # Exactly two scheduled in-week sessions; cancelled is excluded.
    assert body.count("BEGIN:VEVENT") == 2
    # Course code appears in the SUMMARY field.
    assert "TT101" in body
    # The far-future session is excluded by the default range.
    assert body.count("BEGIN:VEVENT") == 2


def test_timetable_ics_range_all_includes_far_future(
    client: APIClient,
    anon_user,  # noqa: ARG001
    in_week_session,  # noqa: ARG001
    out_of_week_session,  # noqa: ARG001
) -> None:
    client.force_authenticate(anon_user)

    response = client.get("/api/v1/exams/timetable.ics?range=all")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    # Both the in-week and the 30-days-out session appear.
    assert body.count("BEGIN:VEVENT") == 2


# ---------------------------------------------------------------------------
# 2) Unauthenticated request returns 401
# ---------------------------------------------------------------------------
def test_timetable_ics_unauthenticated_returns_401(
    client: APIClient,
) -> None:
    response = client.get("/api/v1/exams/timetable.ics")
    assert response.status_code == 401

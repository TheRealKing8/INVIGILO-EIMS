"""Tests for the attendance endpoints.

Nine tests, covering the four custom actions and the three roles
that interact with attendance (invigilator self check-in, student
self check-in, security officer bulk check-in).
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from io import StringIO

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.allocations.models import Allocation, AllocationRun
from apps.attendance.models import CheckIn
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room


pytestmark = pytest.mark.django_db


@pytest.fixture
def session(db):  # type: ignore[no-untyped-def]
    """An exam session scheduled for one hour in the future.

    "One hour in the future" keeps the session comfortably inside
    the punctual window — the invigilator is not late.
    """
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
    start = (date.today() + timedelta(days=7)).isoformat() + "T09:00:00Z"
    end = (date.today() + timedelta(days=7)).isoformat() + "T11:00:00Z"
    return ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at=start, ends_at=end,
        capacity=100, registered=80, invigilators_required=1, status="scheduled",
    )


@pytest.fixture
def past_session(db):  # type: ignore[no-untyped-def]
    """A session that started yesterday — used to test the late flag.

    Anchored to yesterday's date so the test doesn't care what time
    of day the suite runs at: yesterday 09:00 is always at least an
    hour before ``timezone.now()`` no matter what.
    """
    f = Faculty.objects.create(code="F2", name="F2")
    d = Department.objects.create(faculty=f, code="D2", name="D2")
    p = Program.objects.create(department=d, code="P2", name="P2")
    course = Course.objects.create(program=p, code="C2", title="C2", credit_hours=3)
    building = Building.objects.create(code="B2", name="B2")
    room = Room.objects.create(building=building, code="R2", capacity=100)
    period = ExamPeriod.objects.create(
        code="T2", name="Term 2",
        starts_on=date.today() - timedelta(days=1), ends_on=date.today() + timedelta(days=30),
    )
    start = (date.today() - timedelta(days=1)).isoformat() + "T09:00:00Z"
    end = (date.today() - timedelta(days=1)).isoformat() + "T11:00:00Z"
    return ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at=start, ends_at=end,
        capacity=100, registered=80, invigilators_required=1, status="in_progress",
    )


@pytest.fixture
def invigilator_profile(verified_user):  # type: ignore[no-untyped-def]
    profile, _ = InvigilatorProfile.objects.update_or_create(
        user=verified_user, defaults={}
    )
    return profile


@pytest.fixture
def allocation(db, verified_user, invigilator_profile, session):  # type: ignore[no-untyped-def]
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


@pytest.fixture
def security_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="SECURITY_OFFICER",
        defaults={"name": "Security Officer", "is_active": True},
    )
    user = (
        __import__("django.contrib.auth", fromlist=["get_user_model"])
        .get_user_model()
        .objects.create_user(
            email="sec@x.com",
            full_name="Sec",
            password="S3cur3Passw0rd!",
            is_email_verified=True,
        )
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def unallocated_invigilator_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()
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
def grant_permission(db):  # type: ignore[no-untyped-def]
    """Mirrors the project-level fixture (the local one wins by scope)."""
    role, _ = Role.objects.update_or_create(
        code="TEST_RUNTIME", defaults={"name": "Test runtime role", "is_active": True}
    )

    def _grant(user, *codes):  # type: ignore[no-untyped-def]
        for code in codes:
            perm, _ = Permission.objects.update_or_create(
                codename=code, defaults={"name": code}
            )
            RolePermission.objects.update_or_create(role=role, permission=perm)
        UserRole.objects.update_or_create(user=user, role=role)

    return _grant


# ---------------------------------------------------------------------
# 1) Self check-in creates a row
# ---------------------------------------------------------------------
def test_invigilator_self_checkin_creates_row(
    client: APIClient, verified_user, grant_permission, allocation
) -> None:
    grant_permission(verified_user, "attendance.checkin_own", "attendance.view")
    client.force_authenticate(verified_user)
    response = client.post(
        "/api/v1/attendance/",
        {"session_id": str(allocation.session_id), "kind": "invigilator"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["kind"] == "invigilator"
    assert body["method"] == "self"
    assert body["user_email"] == verified_user.email
    assert body["late"] is False
    # Recorded-by equals the user themselves for self check-in.
    assert body["recorded_by_email"] == verified_user.email
    assert CheckIn.objects.filter(
        session_id=allocation.session_id, user=verified_user, kind="invigilator"
    ).count() == 1


# ---------------------------------------------------------------------
# 2) Self check-in is idempotent (200 the second time, no duplicate)
# ---------------------------------------------------------------------
def test_invigilator_self_checkin_idempotent(
    client: APIClient, verified_user, grant_permission, allocation
) -> None:
    grant_permission(verified_user, "attendance.checkin_own", "attendance.view")
    client.force_authenticate(verified_user)
    first = client.post(
        "/api/v1/attendance/",
        {"session_id": str(allocation.session_id), "kind": "invigilator"},
        format="json",
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/attendance/",
        {"session_id": str(allocation.session_id), "kind": "invigilator"},
        format="json",
    )
    assert second.status_code == 200, second.json()
    assert second.json()["id"] == first.json()["id"]
    # Only one row exists.
    assert CheckIn.objects.filter(
        session_id=allocation.session_id, user=verified_user, kind="invigilator"
    ).count() == 1


# ---------------------------------------------------------------------
# 3) Late flag is computed against the session start
# ---------------------------------------------------------------------
def test_invigilator_self_checkin_marks_late(
    client: APIClient, verified_user, grant_permission,
    past_session, invigilator_profile,
) -> None:
    # Confirmed allocation on a session that started an hour ago.
    run = AllocationRun.objects.create(
        period=past_session.period,
        triggered_by=verified_user,
        sessions_total=1, sessions_placed=1,
    )
    Allocation.objects.create(
        run=run, session=past_session, invigilator=invigilator_profile,
        role="invigilator", status="confirmed",
    )
    grant_permission(verified_user, "attendance.checkin_own", "attendance.view")
    client.force_authenticate(verified_user)
    response = client.post(
        "/api/v1/attendance/",
        {"session_id": str(past_session.id), "kind": "invigilator"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert response.json()["late"] is True


# ---------------------------------------------------------------------
# 4) Student self check-in
# ---------------------------------------------------------------------
def test_student_self_checkin_works(
    client: APIClient, student_user, session
) -> None:
    # student_user fixture from apps/accounts/tests/conftest.py
    # already has the STUDENT role and the attendance.checkin_own
    # permission via the 0004 migration.
    client.force_authenticate(student_user)
    response = client.post(
        "/api/v1/attendance/",
        {"session_id": str(session.id), "kind": "student"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert response.json()["kind"] == "student"
    assert response.json()["user_email"] == student_user.email


# ---------------------------------------------------------------------
# 5) An unallocated invigilator cannot self check-in
# ---------------------------------------------------------------------
def test_unallocated_invigilator_cannot_self_checkin(
    client: APIClient, unallocated_invigilator_user, grant_permission, session
) -> None:
    grant_permission(
        unallocated_invigilator_user, "attendance.checkin_own", "attendance.view"
    )
    client.force_authenticate(unallocated_invigilator_user)
    response = client.post(
        "/api/v1/attendance/",
        {"session_id": str(session.id), "kind": "invigilator"},
        format="json",
    )
    assert response.status_code == 403
    # No row created.
    assert CheckIn.objects.filter(user=unallocated_invigilator_user).count() == 0


# ---------------------------------------------------------------------
# 6) Security officer bulk check-in marks several people present
# ---------------------------------------------------------------------
def test_security_bulk_checkin_marks_present(
    client: APIClient, security_user, verified_user, unallocated_invigilator_user,
    student_user, grant_permission, session,
) -> None:
    # The security user needs the bulk + view perms (they get
    # attendance.checkin_any via the SECURITY_OFFICER role, but the
    # grant_permission fixture path is more portable for this test).
    grant_permission(security_user, "attendance.checkin_any", "attendance.view")
    client.force_authenticate(security_user)
    response = client.post(
        f"/api/v1/attendance/sessions/{session.id}/bulk-checkin/",
        {
            "entries": [
                {"user_id": str(verified_user.id), "kind": "invigilator"},
                {"user_id": str(unallocated_invigilator_user.id), "kind": "invigilator"},
                {"user_id": str(student_user.id), "kind": "student"},
            ]
        },
        format="json",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"created": 3, "already": 0}
    bulk_rows = CheckIn.objects.filter(method="bulk", session=session)
    assert bulk_rows.count() == 3
    # The recorded_by is the security user, not the attendee.
    assert all(r.recorded_by_id == security_user.id for r in bulk_rows)


# ---------------------------------------------------------------------
# 7) Bulk check-in is idempotent
# ---------------------------------------------------------------------
def test_security_bulk_checkin_idempotent(
    client: APIClient, security_user, verified_user, unallocated_invigilator_user,
    student_user, grant_permission, session,
) -> None:
    grant_permission(security_user, "attendance.checkin_any", "attendance.view")
    client.force_authenticate(security_user)
    payload = {
        "entries": [
            {"user_id": str(verified_user.id), "kind": "invigilator"},
            {"user_id": str(unallocated_invigilator_user.id), "kind": "invigilator"},
            {"user_id": str(student_user.id), "kind": "student"},
        ]
    }
    first = client.post(
        f"/api/v1/attendance/sessions/{session.id}/bulk-checkin/", payload, format="json"
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/v1/attendance/sessions/{session.id}/bulk-checkin/", payload, format="json"
    )
    assert second.status_code == 200
    assert second.json() == {"created": 0, "already": 3}


# ---------------------------------------------------------------------
# 8) Roster returns expected present / expected / late counts
# ---------------------------------------------------------------------
def test_roster_returns_expected_counts(
    client: APIClient, security_user, verified_user, unallocated_invigilator_user,
    student_user, grant_permission, allocation, session,
) -> None:
    grant_permission(security_user, "attendance.checkin_any", "attendance.view")
    client.force_authenticate(security_user)
    # Self check-in for the allocated invigilator, bulk check-in for
    # the unallocated invigilator + the student.
    client.force_authenticate(verified_user)
    r = client.post(
        "/api/v1/attendance/",
        {"session_id": str(session.id), "kind": "invigilator"},
        format="json",
    )
    assert r.status_code == 201, r.json()
    client.force_authenticate(security_user)
    client.post(
        f"/api/v1/attendance/sessions/{session.id}/bulk-checkin/",
        {
            "entries": [
                {"user_id": str(unallocated_invigilator_user.id), "kind": "invigilator"},
                {"user_id": str(student_user.id), "kind": "student"},
            ]
        },
        format="json",
    )
    # Fetch the roster as the security user.
    response = client.get(f"/api/v1/attendance/sessions/{session.id}/roster/")
    assert response.status_code == 200, response.json()
    body = response.json()
    # The allocated invigilator (verified_user) is the only
    # *expected* invigilator; the unallocated one was bulk-checked
    # in but isn't on the expected list (security can do this — the
    # extra row just doesn't count toward "expected" in the totals).
    assert body["totals"]["invigilator"]["expected"] == 1
    assert body["totals"]["invigilator"]["present"] == 1
    assert body["totals"]["invigilator"]["late"] == 0
    # session.registered = 80 students expected; only 1 present.
    assert body["totals"]["student"]["expected"] == 80
    assert body["totals"]["student"]["present"] == 1


# ---------------------------------------------------------------------
# 9) CSV export returns a text/csv attachment
# ---------------------------------------------------------------------
def test_csv_export_returns_attachment(
    client: APIClient, verified_user, grant_permission, allocation, session
) -> None:
    grant_permission(verified_user, "attendance.checkin_own", "attendance.view")
    client.force_authenticate(verified_user)
    client.post(
        "/api/v1/attendance/",
        {"session_id": str(session.id), "kind": "invigilator", "location": "Main door"},
        format="json",
    )
    response = client.get(f"/api/v1/attendance/sessions/{session.id}/export.csv")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]
    body = response.content.decode("utf-8")
    reader = csv.reader(StringIO(body))
    rows = list(reader)
    # Header + at least one invigilator row.
    assert rows[0][0] == "kind"
    assert any(r[0] == "invigilator" and r[3] == verified_user.full_name for r in rows[1:])

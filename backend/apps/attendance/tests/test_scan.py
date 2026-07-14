"""Tests for the QR scan endpoint (``POST /attendance/scan/``).

The endpoint is the security officer's primary door action — the
device scans a student's QR (or the secops types the student_code
fallback), the body is looked up as a :class:`StudentRegistration`,
and a :class:`CheckIn` is created. Five tests:

1. Happy path — scan creates a row.
2. Idempotent — second scan returns the same row, no duplicate.
3. 404 — registration that doesn't belong to the session.
4. 403 — student without ``attendance.checkin_any`` is denied.
5. Signature is stored when provided (data-URL prefix is stripped).
"""
from __future__ import annotations

import base64
import uuid

import pytest
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.attendance.models import CheckIn
from apps.exams.models import ExamPeriod, ExamSession
from apps.exams.student_registration import StudentRegistration
from apps.rooms.models import Building, Room

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures (local — see apps/incidents/tests/test_api.py:session for why we
# can't import the attendance test suite's fixtures from a sibling app)
# ---------------------------------------------------------------------------
@pytest.fixture
def session(db):  # type: ignore[no-untyped-def]
    f = Faculty.objects.create(code="F", name="F")
    d = Department.objects.create(faculty=f, code="D", name="D")
    p = Program.objects.create(department=d, code="P", name="P")
    course = Course.objects.create(program=p, code="C", title="C", credit_hours=3)
    building = Building.objects.create(code="B", name="B")
    room = Room.objects.create(building=building, code="R", capacity=100)
    period = ExamPeriod.objects.create(
        code="T1", name="T1",
        starts_on="2026-08-01", ends_on="2026-08-30",
    )
    return ExamSession.objects.create(
        period=period, course=course, room=room,
        starts_at="2026-08-15T09:00:00Z", ends_at="2026-08-15T11:00:00Z",
        capacity=100, registered=80, invigilators_required=1, status="scheduled",
    )


@pytest.fixture
def student_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="STUDENT", defaults={"name": "Student", "is_active": True}
    )
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user(
        email="stu@x.com", full_name="Stu", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def security_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="SECURITY_OFFICER", defaults={"name": "Security Officer", "is_active": True}
    )
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user(
        email="sec@x.com", full_name="Sec", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def registration(session, student_user):  # type: ignore[no-untyped-def]
    return StudentRegistration.objects.create(
        session=session, student=student_user, student_code="C-2026-0001"
    )


@pytest.fixture
def grant_permission(db):  # type: ignore[no-untyped-def]
    """Mirror the project-level fixture; the local one wins by scope."""
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


# ---------------------------------------------------------------------------
# 1) Happy path
# ---------------------------------------------------------------------------
def test_scan_creates_checkin(
    client: APIClient, security_user, grant_permission, session, registration
) -> None:
    grant_permission(security_user, "attendance.checkin_any")
    client.force_authenticate(security_user)
    response = client.post(
        "/api/v1/attendance/scan/",
        {
            "session_id": str(session.id),
            "registration_id": str(registration.id),
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["kind"] == "student"
    assert body["method"] == "bulk"
    assert body["user_email"] == registration.student.email
    assert body["recorded_by_email"] == security_user.email
    # Exactly one row.
    assert CheckIn.objects.filter(
        session=session, user=registration.student, kind="student"
    ).count() == 1


# ---------------------------------------------------------------------------
# 2) Idempotent
# ---------------------------------------------------------------------------
def test_scan_is_idempotent(
    client: APIClient, security_user, grant_permission, session, registration
) -> None:
    grant_permission(security_user, "attendance.checkin_any")
    client.force_authenticate(security_user)
    payload = {
        "session_id": str(session.id),
        "registration_id": str(registration.id),
    }
    first = client.post("/api/v1/attendance/scan/", payload, format="json")
    second = client.post("/api/v1/attendance/scan/", payload, format="json")
    assert first.status_code == 201
    assert second.status_code == 200, second.json()
    assert second.json()["id"] == first.json()["id"]
    assert CheckIn.objects.filter(
        session=session, user=registration.student, kind="student"
    ).count() == 1


# ---------------------------------------------------------------------------
# 3) Registration not for this session
# ---------------------------------------------------------------------------
def test_scan_404_for_unregistered_student(
    client: APIClient, security_user, grant_permission, session, student_user
) -> None:
    """A registration that exists but is for a different session must 404."""
    # Build a second session and register the student against it.
    other_period = ExamPeriod.objects.create(
        code="T2", name="T2", starts_on="2026-09-01", ends_on="2026-09-30",
    )
    other_session = ExamSession.objects.create(
        period=other_period, course=session.course, room=session.room,
        starts_at="2026-09-15T09:00:00Z", ends_at="2026-09-15T11:00:00Z",
        capacity=100, registered=80, invigilators_required=1, status="scheduled",
    )
    other_reg = StudentRegistration.objects.create(
        session=other_session, student=student_user, student_code="C-2026-9001"
    )
    grant_permission(security_user, "attendance.checkin_any")
    client.force_authenticate(security_user)
    response = client.post(
        "/api/v1/attendance/scan/",
        {
            "session_id": str(session.id),  # session A
            "registration_id": str(other_reg.id),  # but registration for session B
        },
        format="json",
    )
    assert response.status_code == 404
    # No row was created.
    assert CheckIn.objects.count() == 0


# ---------------------------------------------------------------------------
# 4) Student without the codename cannot scan
# ---------------------------------------------------------------------------
def test_scan_403_without_checkin_any(
    client: APIClient, student_user, session, registration
) -> None:
    # student_user has the STUDENT role and ``attendance.checkin_own``
    # but not ``attendance.checkin_any`` (that's security officer only).
    client.force_authenticate(student_user)
    response = client.post(
        "/api/v1/attendance/scan/",
        {
            "session_id": str(session.id),
            "registration_id": str(registration.id),
        },
        format="json",
    )
    assert response.status_code == 403
    assert CheckIn.objects.count() == 0


# ---------------------------------------------------------------------------
# 5) Signature is stored (data-URL prefix stripped)
# ---------------------------------------------------------------------------
def test_scan_with_signature_stores_image(
    client: APIClient, security_user, grant_permission, session, registration
) -> None:
    grant_permission(security_user, "attendance.checkin_any")
    client.force_authenticate(security_user)
    # 8-byte payload ("signature" in base64) — decodes to "c2lnbmF0dXJl".
    bare = base64.b64encode(b"signature").decode("ascii")
    payload = {
        "session_id": str(session.id),
        "registration_id": str(registration.id),
        "signature_png": f"data:image/png;base64,{bare}",
    }
    response = client.post("/api/v1/attendance/scan/", payload, format="json")
    assert response.status_code == 201, response.json()
    row = CheckIn.objects.get(
        session=session, user=registration.student, kind="student"
    )
    # The stored value is the bare base64 — no data-URL prefix.
    assert row.signature_image == bare
    assert "data:image" not in row.signature_image

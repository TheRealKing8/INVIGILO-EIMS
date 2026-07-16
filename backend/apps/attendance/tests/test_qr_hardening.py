"""Tests for the Phase 19 QR hardening.

Eight tests, split across the two new surfaces (the QrToken model
+ service, and the live feed endpoint) plus regressions on the
existing scan path. The new model introduces four threat-model
assertions:

  1. A fresh token round-trips (issue → verify).
  2. A tampered signature is rejected.
  3. An expired token is rejected.
  4. A revoked token is rejected even if the signature is valid.

The scan endpoint adds three more:

  5. A signed student token resolves to a check-in.
  6. A signed staff token resolves to an invigilator check-in.
  7. A token from the wrong session is rejected.

And the live feed gets one more:

  8. The live feed returns the most recent N rows in reverse order.
"""
from __future__ import annotations

import base64
import io
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.allocations.models import Allocation, AllocationRun
from apps.attendance.models import CheckIn
from apps.exams.models import ExamPeriod, ExamSession
from apps.exams.qr_tokens import (
    STAFF_TOKEN_TTL_SECONDS,
    STUDENT_TOKEN_TTL_SECONDS,
    QrTokenInvalid,
    QrTokenRevoked,
    QrTokenUnknown,
    issue_staff_qr_token,
    issue_student_qr_token,
    verify_qr_token,
)
from apps.exams.student_registration import QrToken, StudentRegistration
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room

User = get_user_model()
pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
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
        code="T1", name="T1", starts_on="2026-08-01", ends_on="2026-08-30",
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
    user = User.objects.create_user(
        email="stu@x.com", full_name="Stu", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def staff_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    user = User.objects.create_user(
        email="inv@x.com", full_name="Inv", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    InvigilatorProfile.objects.update_or_create(user=user, defaults={})
    return user


@pytest.fixture
def security_user(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="SECURITY_OFFICER", defaults={"name": "Security Officer", "is_active": True}
    )
    user = User.objects.create_user(
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
# 1) Fresh token round-trips
# ---------------------------------------------------------------------------
def test_qr_token_round_trip(registration) -> None:
    raw, row = issue_student_qr_token(registration)
    assert row.kind == "student"
    assert row.scope == "session"
    assert row.session_id == registration.session_id
    # The row carries the hash, not the raw token.
    assert raw not in (row.token_hash,)
    # verify_qr_token returns the live row.
    verified = verify_qr_token(raw)
    assert verified.id == row.id


# ---------------------------------------------------------------------------
# 2) Tampered signature is rejected
# ---------------------------------------------------------------------------
def test_qr_token_rejects_tampered_signature(registration) -> None:
    raw, _ = issue_student_qr_token(registration)
    subject, exp, nonce, sig = raw.split(":")
    # Flip a hex digit at the end of the signature.
    bad_sig = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    tampered = f"{subject}:{exp}:{nonce}:{bad_sig}"
    with pytest.raises(QrTokenInvalid):
        verify_qr_token(tampered)


# ---------------------------------------------------------------------------
# 3) Expired token is rejected
# ---------------------------------------------------------------------------
def test_qr_token_rejects_expired(registration) -> None:
    raw, _ = issue_student_qr_token(registration, ttl_seconds=1)
    # Move "now" forward 60s without sleeping.
    future = datetime.now(tz=timezone.utc) + timedelta(seconds=60)
    with patch("apps.exams.qr_tokens.timezone.now", return_value=future):
        with pytest.raises(QrTokenInvalid) as exc:
            verify_qr_token(raw)
        assert "expired" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 4) Revoked token is rejected
# ---------------------------------------------------------------------------
def test_qr_token_rejects_revoked(registration) -> None:
    raw, row = issue_student_qr_token(registration)
    row.revoked_at = datetime.now(tz=timezone.utc)
    row.save(update_fields=["revoked_at", "updated_at"])
    with pytest.raises(QrTokenRevoked):
        verify_qr_token(raw)


# ---------------------------------------------------------------------------
# 5) Scan with a signed student token creates a check-in
# ---------------------------------------------------------------------------
def test_scan_with_student_token_creates_checkin(
    client: APIClient, security_user, grant_permission, session, registration
) -> None:
    grant_permission(security_user, "attendance.checkin_any")
    raw, _ = issue_student_qr_token(registration)
    client.force_authenticate(security_user)
    response = client.post(
        "/api/v1/attendance/scan/",
        {"session_id": str(session.id), "token": raw},
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["kind"] == "student"
    assert body["user_email"] == registration.student.email
    assert CheckIn.objects.filter(
        session=session, user=registration.student, kind="student"
    ).count() == 1


# ---------------------------------------------------------------------------
# 6) Scan with a signed staff token creates an invigilator check-in
# ---------------------------------------------------------------------------
def test_scan_with_staff_token_creates_checkin(
    client: APIClient, security_user, grant_permission, session, staff_user
) -> None:
    grant_permission(security_user, "attendance.checkin_any")
    raw, _ = issue_staff_qr_token(staff_user)
    client.force_authenticate(security_user)
    response = client.post(
        "/api/v1/attendance/scan/",
        {"session_id": str(session.id), "token": raw},
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["user_email"] == staff_user.email
    assert body["kind"] == "invigilator"
    # Not an allocated invigilator → location is the sentinel "staff".
    assert body["location"] == "staff"
    assert CheckIn.objects.filter(
        session=session, user=staff_user, kind="invigilator"
    ).count() == 1


# ---------------------------------------------------------------------------
# 7) Token from the wrong session is rejected
# ---------------------------------------------------------------------------
def test_scan_rejects_token_for_other_session(
    client: APIClient, security_user, grant_permission, session, registration
) -> None:
    """A signed student token is bound to a session. The scanner is
    operating on a different session; the call must be rejected."""
    grant_permission(security_user, "attendance.checkin_any")
    # Build a different session and ask the scanner to use it.
    other_period = ExamPeriod.objects.create(
        code="T2", name="T2", starts_on="2026-09-01", ends_on="2026-09-30",
    )
    other_session = ExamSession.objects.create(
        period=other_period, course=session.course, room=session.room,
        starts_at="2026-09-15T09:00:00Z", ends_at="2026-09-15T11:00:00Z",
        capacity=100, registered=80, invigilators_required=1, status="scheduled",
    )
    raw, _ = issue_student_qr_token(registration)
    client.force_authenticate(security_user)
    response = client.post(
        "/api/v1/attendance/scan/",
        {"session_id": str(other_session.id), "token": raw},
        format="json",
    )
    assert response.status_code == 400
    assert "session" in response.json()["detail"].lower()
    # No check-in was created on either session.
    assert CheckIn.objects.count() == 0


# ---------------------------------------------------------------------------
# 8) Live feed returns the last 20 check-ins, most recent first
# ---------------------------------------------------------------------------
def test_live_feed_returns_recent_checkins(
    client: APIClient, security_user, grant_permission, session
) -> None:
    grant_permission(security_user, "attendance.view")
    # The (session, user, kind) unique constraint means each row needs
    # a distinct user. Create 25 students and register 25 check-ins
    # (one per user, all of kind=STUDENT) so the assertion can
    # confirm exactly 20 are returned (the most recent 20).
    stu_role, _ = Role.objects.update_or_create(
        code="STUDENT", defaults={"name": "Student", "is_active": True}
    )
    now = datetime.now(tz=timezone.utc)
    for i in range(25):
        u = User.objects.create_user(
            email=f"u{i}@x.com", full_name=f"U{i}",
            password="S3cur3Passw0rd!", is_email_verified=True,
        )
        UserRole.objects.create(user=u, role=stu_role)
        CheckIn.objects.create(
            session=session,
            user=u,
            kind=CheckIn.Kind.STUDENT,
            method=CheckIn.Method.BULK,
            late=False,
            at=now - timedelta(minutes=30 - i),
            recorded_by=security_user,
        )
    client.force_authenticate(security_user)
    response = client.get(f"/api/v1/attendance/sessions/{session.id}/live/")
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["session_id"] == str(session.id)
    entries = body["entries"]
    assert len(entries) == 20
    # Most recent first: the last-inserted row is at the top.
    assert entries[0]["at"] >= entries[1]["at"]
    # Each entry has the denormalised fields the UI needs.
    assert "user_email" in entries[0]
    assert "kind" in entries[0]
    assert "late" in entries[0]

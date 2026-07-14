"""Tests for the e-signature on the existing bulk check-in path.

The bulk endpoint also accepts a ``signature_png`` field on each
entry — Phase 15 lets the security officer draw a signature once
and submit it with the bulk row. The same "first scan wins" rule
applies: a second bulk check-in for the same (session, user, kind)
does NOT overwrite the stored signature.
"""
from __future__ import annotations

import base64

import pytest
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.attendance.models import CheckIn
from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import InvigilatorProfile
from apps.rooms.models import Building, Room

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures — minimal versions of the suites in test_api.py / conftest.py
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
def target_user(db):  # type: ignore[no-untyped-def]
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        email="t@x.com", full_name="Target", password="S3cur3Passw0rd!",
        is_email_verified=True,
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
# 1) Bulk check-in with a signature stores the image
# ---------------------------------------------------------------------------
def test_bulk_checkin_accepts_signature(
    client: APIClient, security_user, target_user, grant_permission, session
) -> None:
    grant_permission(security_user, "attendance.checkin_any")
    client.force_authenticate(security_user)
    bare = base64.b64encode(b"first-signature").decode("ascii")
    response = client.post(
        f"/api/v1/attendance/sessions/{session.id}/bulk-checkin/",
        {
            "entries": [
                {
                    "user_id": str(target_user.id),
                    "kind": "student",
                    "signature_png": bare,
                }
            ]
        },
        format="json",
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"created": 1, "already": 0}
    row = CheckIn.objects.get(session=session, user=target_user)
    assert row.signature_image == bare


# ---------------------------------------------------------------------------
# 2) Second check-in does not overwrite the existing signature
# ---------------------------------------------------------------------------
def test_existing_checkin_does_not_overwrite_signature(
    client: APIClient, security_user, target_user, grant_permission, session
) -> None:
    grant_permission(security_user, "attendance.checkin_any")
    client.force_authenticate(security_user)
    first = base64.b64encode(b"first").decode("ascii")
    second = base64.b64encode(b"second-attempt").decode("ascii")
    # First call creates the row with sig1.
    client.post(
        f"/api/v1/attendance/sessions/{session.id}/bulk-checkin/",
        {"entries": [{"user_id": str(target_user.id), "kind": "student", "signature_png": first}]},
        format="json",
    )
    # Second call with sig2 is a no-op for the row itself — the
    # existing signature must NOT be overwritten.
    response = client.post(
        f"/api/v1/attendance/sessions/{session.id}/bulk-checkin/",
        {"entries": [{"user_id": str(target_user.id), "kind": "student", "signature_png": second}]},
        format="json",
    )
    assert response.status_code == 200
    assert response.json() == {"created": 0, "already": 1}
    row = CheckIn.objects.get(session=session, user=target_user)
    assert row.signature_image == first

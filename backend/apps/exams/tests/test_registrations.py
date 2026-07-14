"""Tests for the StudentRegistration viewset + the QR endpoint.

The new model and viewset are the spine of Phase 15's door-scanner
flow. Five tests:

  1. List filters by session.
  2. Create is idempotent on (session, student) — second POST is 400.
  3. The QR endpoint returns a real PNG.
  4. ``ensure_registrations`` populates from every active STUDENT user.
  5. ``student_code`` is unique per session.
"""
from __future__ import annotations

import io
from datetime import datetime

import pytest
from rest_framework.test import APIClient

from apps.academic.models import Course, Department, Faculty, Program
from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.exams.models import ExamPeriod, ExamSession
from apps.exams.services import ensure_registrations, generate_student_code
from apps.exams.student_registration import StudentRegistration
from apps.rooms.models import Building, Room

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def exam_period(db):  # type: ignore[no-untyped-def]
    return ExamPeriod.objects.create(
        code="P1", name="Period 1", starts_on="2026-08-01", ends_on="2026-08-30"
    )


@pytest.fixture
def course(db):  # type: ignore[no-untyped-def]
    f = Faculty.objects.create(code="F", name="F")
    d = Department.objects.create(faculty=f, code="D", name="D")
    p = Program.objects.create(department=d, code="P", name="P")
    return Course.objects.create(program=p, code="REG101", title="Intro", credit_hours=3)


@pytest.fixture
def session(course, exam_period):  # type: ignore[no-untyped-def]
    building = Building.objects.create(code="B", name="B")
    room = Room.objects.create(building=building, code="R", capacity=100)
    return ExamSession.objects.create(
        period=exam_period, course=course, room=room,
        starts_at=datetime.fromisoformat("2026-08-15T09:00:00+00:00"),
        ends_at=datetime.fromisoformat("2026-08-15T11:00:00+00:00"),
        capacity=100, registered=80, invigilators_required=1, status="scheduled",
    )


@pytest.fixture
def other_session(course, exam_period):  # type: ignore[no-untyped-def]
    return ExamSession.objects.create(
        period=exam_period, course=course,
        starts_at=datetime.fromisoformat("2026-08-20T09:00:00+00:00"),
        ends_at=datetime.fromisoformat("2026-08-20T11:00:00+00:00"),
        capacity=100, registered=80, invigilators_required=1, status="scheduled",
    )


@pytest.fixture
def student_role(db):  # type: ignore[no-untyped-def]
    role, _ = Role.objects.update_or_create(
        code="STUDENT", defaults={"name": "Student", "is_active": True}
    )
    return role


@pytest.fixture
def make_student(student_role):  # type: ignore[no-untyped-def]
    from django.contrib.auth import get_user_model

    User = get_user_model()

    def _make(email: str, full_name: str = "Stu"):  # type: ignore[no-untyped-def]
        user = User.objects.create_user(
            email=email, full_name=full_name, password="S3cur3Passw0rd!",
            is_email_verified=True,
        )
        UserRole.objects.create(user=user, role=student_role)
        return user

    return _make


@pytest.fixture
def officer_user(db):  # type: ignore[no-untyped-def]
    """An EO with the broad ``exam.session.crud`` perm (and friends)."""
    role, _ = Role.objects.update_or_create(
        code="EXAMINATION_OFFICER",
        defaults={"name": "Examination Officer", "is_active": True},
    )
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user(
        email="eo@x.com", full_name="Officer", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=role)
    for code in ("exam.session.crud", "people.student.crud", "attendance.view"):
        perm, _ = Permission.objects.update_or_create(
            codename=code, defaults={"name": code}
        )
        RolePermission.objects.update_or_create(role=role, permission=perm)
    return user


# ---------------------------------------------------------------------------
# 1) List filters by session
# ---------------------------------------------------------------------------
def test_list_registrations_filters_by_session(
    client: APIClient, officer_user, session, other_session, make_student
) -> None:
    a1 = make_student("a1@x.com", "A1")
    a2 = make_student("a2@x.com", "A2")
    b1 = make_student("b1@x.com", "B1")
    StudentRegistration.objects.create(session=session, student=a1, student_code="C-2026-0001")
    StudentRegistration.objects.create(session=session, student=a2, student_code="C-2026-0002")
    StudentRegistration.objects.create(session=other_session, student=b1, student_code="C-2026-0003")
    client.force_authenticate(officer_user)
    response = client.get(f"/api/v1/exams/registrations/?session={session.id}")
    assert response.status_code == 200
    data = response.json()
    # Paginated response has a 'results' key.
    results = data.get("results") if isinstance(data, dict) else data
    codes = sorted(r["student_code"] for r in results)
    assert codes == ["C-2026-0001", "C-2026-0002"]


# ---------------------------------------------------------------------------
# 2) Create is idempotent on (session, student)
# ---------------------------------------------------------------------------
def test_create_registration_is_idempotent(
    client: APIClient, officer_user, session, make_student
) -> None:
    student = make_student("dup@x.com")
    client.force_authenticate(officer_user)
    first = client.post(
        "/api/v1/exams/registrations/",
        {
            "session": str(session.id),
            "student": str(student.id),
            "student_code": "C-2026-0042",
        },
        format="json",
    )
    assert first.status_code == 201, first.json()
    second = client.post(
        "/api/v1/exams/registrations/",
        {
            "session": str(session.id),
            "student": str(student.id),
            "student_code": "C-2026-0042",
        },
        format="json",
    )
    assert second.status_code == 400, second.json()
    # Only one row exists.
    assert StudentRegistration.objects.filter(
        session=session, student=student
    ).count() == 1


# ---------------------------------------------------------------------------
# 3) QR endpoint returns a real PNG
# ---------------------------------------------------------------------------
def test_qr_png_returns_image(
    client: APIClient, officer_user, session, make_student
) -> None:
    student = make_student("qr@x.com")
    reg = StudentRegistration.objects.create(
        session=session, student=student, student_code="C-2026-0001"
    )
    client.force_authenticate(officer_user)
    response = client.get(f"/api/v1/exams/registrations/{reg.id}/qr.png/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    # PNG magic number.
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
    # And Pillow can open it.
    from PIL import Image

    img = Image.open(io.BytesIO(response.content))
    img.verify()
    assert img.size[0] > 0 and img.size[1] > 0


# ---------------------------------------------------------------------------
# 4) ensure_registrations populates from every active STUDENT user
# ---------------------------------------------------------------------------
def test_ensure_registrations_populates_from_department(
    session, make_student
) -> None:
    a = make_student("a@x.com", "A")
    b = make_student("b@x.com", "B")
    c = make_student("c@x.com", "C")
    # Inactive student is skipped.
    from django.contrib.auth import get_user_model

    inactive = get_user_model().objects.create_user(
        email="off@x.com", full_name="Off", password="S3cur3Passw0rd!",
        is_email_verified=True, is_active=False,
    )
    # Non-student user is skipped.
    from apps.accounts.models import Role as RoleModel

    inv_role, _ = RoleModel.objects.update_or_create(
        code="INVIGILATOR", defaults={"name": "Invigilator", "is_active": True}
    )
    inv = get_user_model().objects.create_user(
        email="inv@x.com", full_name="Inv", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=inv, role=inv_role)

    created = ensure_registrations(session)
    assert created == 3
    # Idempotent: second call is a no-op.
    again = ensure_registrations(session)
    assert again == 0
    # Exactly the three active students got registered.
    emails = sorted(
        StudentRegistration.objects.filter(session=session).values_list(
            "student__email", flat=True
        )
    )
    assert emails == [a.email, b.email, c.email]
    # The inactive + invigilator users are not present.
    assert not StudentRegistration.objects.filter(student=inactive).exists()
    assert not StudentRegistration.objects.filter(student=inv).exists()


# ---------------------------------------------------------------------------
# 5) student_code is unique per session
# ---------------------------------------------------------------------------
def test_student_code_is_unique_per_session(session, make_student) -> None:
    a = make_student("a@x.com", "A")
    b = make_student("b@x.com", "B")
    StudentRegistration.objects.create(
        session=session, student=a, student_code=generate_student_code(session, 1)
    )
    StudentRegistration.objects.create(
        session=session, student=b, student_code=generate_student_code(session, 2)
    )
    codes = list(
        StudentRegistration.objects.filter(session=session).values_list(
            "student_code", flat=True
        )
    )
    assert len(codes) == 2
    assert len(set(codes)) == 2
    # Sanity: the helper formats the code with the course + year.
    assert all(c.startswith("REG101-2026-") for c in codes)

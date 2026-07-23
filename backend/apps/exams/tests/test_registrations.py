"""Tests for the StudentRegistration viewset + the QR endpoint.

The new model and viewset are the spine of Phase 15's door-scanner
flow. Five tests:

  1. List filters by session.
  2. Create is idempotent on (session, student) — second POST is 400.
  3. The QR endpoint returns a real PNG.
  4. ``ensure_registrations`` populates from every active STUDENT user.
  5. ``student_code`` is unique per session.

Phase 25 added the student self-service QR card. The viewset now
scopes the queryset to ``student == request.user`` for narrow
readers (the ``exam.registration.view_own`` codename), so a
student can only see their own row + QR. Five more tests
in :class:`TestStudentOwnScope` cover that contract.
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


# ---------------------------------------------------------------------------
# Phase 25 — STUDENT self-service QR
# ---------------------------------------------------------------------------
# The viewset's get_queryset override narrows the read to
# ``student == request.user`` for narrow readers (the
# ``exam.registration.view_own`` codename). These tests cover the
# contract: list/retrieve/qr_png scope to the caller, PII fields
# stay hidden on rows the caller doesn't own, and wide readers
# (operations) are unaffected.
# ---------------------------------------------------------------------------


@pytest.fixture
def student_with_self_qr_perm(student_role):  # type: ignore[no-untyped-def]
    """A STUDENT user that also holds ``exam.registration.view_own``.

    The ``make_student`` fixture already attaches the STUDENT role
    to the user; here we just need to *add* the single codename
    that the viewset's read perm set requires. The codename lookup
    is idempotent so a parallel test run (which would have already
    seeded the perm via the 0003 migration) still works.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    perm, _ = Permission.objects.update_or_create(
        codename="exam.registration.view_own",
        defaults={"name": "View own student registration + QR"},
    )
    RolePermission.objects.update_or_create(
        role=student_role, permission=perm
    )
    user = User.objects.create_user(
        email="self@x.com", full_name="Self", password="S3cur3Passw0rd!",
        is_email_verified=True,
    )
    UserRole.objects.create(user=user, role=student_role)
    return user


def test_student_list_filters_to_own_rows(
    client: APIClient, student_with_self_qr_perm, session, make_student
) -> None:
    """A narrow-read student only sees their own row.

    Two other students have registrations on the same session; the
    student with ``exam.registration.view_own`` only sees the row
    where ``student == self``.
    """
    me = student_with_self_qr_perm
    other1 = make_student("other1@x.com", "Other1")
    other2 = make_student("other2@x.com", "Other2")
    StudentRegistration.objects.create(
        session=session, student=me, student_code="SELF-001"
    )
    StudentRegistration.objects.create(
        session=session, student=other1, student_code="O-001"
    )
    StudentRegistration.objects.create(
        session=session, student=other2, student_code="O-002"
    )
    client.force_authenticate(me)
    response = client.get("/api/v1/exams/registrations/")
    assert response.status_code == 200
    data = response.json()
    results = data.get("results") if isinstance(data, dict) else data
    codes = sorted(r["student_code"] for r in results)
    assert codes == ["SELF-001"], (
        f"student should only see their own row, got {codes!r}"
    )
    # And the row's student field is the caller's own id.
    assert results[0]["student"] == str(me.id)


def test_student_cannot_fetch_other_students_qr(
    client: APIClient, student_with_self_qr_perm, session, make_student
) -> None:
    """A narrow-read student gets 404 when fetching another student's QR.

    The ``qr_png`` action goes through ``self.get_object()``, which
    uses the narrowed queryset. The DRF default for a missing
    object is 404, not 403 — that's deliberate, see the docstring
    on the viewset.
    """
    other = make_student("other@x.com", "Other")
    reg = StudentRegistration.objects.create(
        session=session, student=other, student_code="O-001"
    )
    client.force_authenticate(student_with_self_qr_perm)
    response = client.get(f"/api/v1/exams/registrations/{reg.id}/qr.png/")
    assert response.status_code == 404, response.content


def test_student_can_fetch_own_qr(
    client: APIClient, student_with_self_qr_perm, session
) -> None:
    """A narrow-read student CAN fetch their own QR PNG.

    The PNG should be a real image (PNG magic number + Pillow can
    open it). Mirrors ``test_qr_png_returns_image`` above but
    with a student auth.
    """
    me = student_with_self_qr_perm
    reg = StudentRegistration.objects.create(
        session=session, student=me, student_code="SELF-001"
    )
    client.force_authenticate(me)
    response = client.get(f"/api/v1/exams/registrations/{reg.id}/qr.png/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    # PNG magic number.
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
    from PIL import Image

    img = Image.open(io.BytesIO(response.content))
    img.verify()
    assert img.size[0] > 0 and img.size[1] > 0


def test_student_list_does_not_leak_other_emails(
    client: APIClient, student_with_self_qr_perm, session, make_student
) -> None:
    """Defence-in-depth: even if a row leaks, no email/name is exposed.

    The viewset's ``get_queryset`` already filters to the
    caller's own row, so the PII fields on *someone else's* row
    are unreachable via the list endpoint. This test makes that
    guarantee explicit by asserting that the PII fields are
    ``None`` for any row whose ``student_id`` is not the viewer.
    It's belt-and-braces — if a future refactor widens the
    queryset, this test will catch the regression.
    """
    from rest_framework.test import APIRequestFactory

    from apps.exams.serializers import StudentRegistrationSerializer

    me = student_with_self_qr_perm
    other = make_student("leak@x.com", "Leak")
    StudentRegistration.objects.create(
        session=session, student=me, student_code="SELF-001"
    )
    other_reg = StudentRegistration.objects.create(
        session=session, student=other, student_code="O-001"
    )

    factory = APIRequestFactory()
    request = factory.get("/api/v1/exams/registrations/")
    request.user = me

    # The caller's own row: PII visible.
    ser_self = StudentRegistrationSerializer(
        StudentRegistration.objects.get(student=me), context={"request": request}
    )
    assert ser_self.data["student_email"] == me.email
    assert ser_self.data["student_name"] == me.full_name

    # Another student's row: PII hidden, even though the row is
    # technically still in the DB. (The viewset's get_queryset
    # would 404 before the serializer runs in practice; this
    # test pins the defence-in-depth gate.)
    ser_other = StudentRegistrationSerializer(other_reg, context={"request": request})
    assert ser_other.data["student_email"] is None
    assert ser_other.data["student_name"] is None


def test_eo_still_sees_full_roster(
    client: APIClient, officer_user, session, student_with_self_qr_perm, make_student
) -> None:
    """Regression: the EO roster + email/name rendering is unchanged.

    Wide readers (anyone holding ``exam.session.crud`` /
    ``people.student.crud`` / ``attendance.view``) bypass the
    ``student == user`` filter and see every row with PII
    populated. This is what the EO roster page at
    ``/dashboard/exams/[id]/registrations`` relies on.
    """
    me = student_with_self_qr_perm
    other = make_student("other@x.com", "Other Student")
    StudentRegistration.objects.create(
        session=session, student=me, student_code="SELF-001"
    )
    StudentRegistration.objects.create(
        session=session, student=other, student_code="O-001"
    )
    client.force_authenticate(officer_user)
    response = client.get(f"/api/v1/exams/registrations/?session={session.id}")
    assert response.status_code == 200
    data = response.json()
    results = data.get("results") if isinstance(data, dict) else data
    codes = sorted(r["student_code"] for r in results)
    assert codes == ["O-001", "SELF-001"], (
        f"officer should see every row, got {codes!r}"
    )
    # And PII is populated for both rows.
    for row in results:
        assert row["student_email"]
        assert row["student_name"]

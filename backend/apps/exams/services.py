"""Service layer for the ``exams`` app.

Phase 15 adds two helpers used by the new ``StudentRegistration``
workflow:

  * :func:`ensure_registrations` — populate a session's roster with
    a row per active STUDENT user. Idempotent: re-running doesn't
    duplicate existing rows.
  * :func:`generate_student_code` — produce a short, human-readable
    label of the form ``{course_code}-{year}-{seq:04d}`` (e.g.
    ``CS101-2026-0042``). Sequential per session.

The current model has no link between a ``User`` and an academic
``Program`` or ``Department`` — students are just ``User`` rows with
the ``STUDENT`` role. So the populator registers *every* active
STUDENT in the system for the session. A future Phase 17 CSV import
can replace this with a per-program roster.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import ExamSession
from .student_registration import StudentRegistration

User = get_user_model()


def generate_student_code(session: ExamSession, seq: int) -> str:
    """Build a short label like ``CS101-2026-0042``.

    ``seq`` is 1-indexed within the session (the first registration
    gets ``0001``). The course code and the year are pulled off the
    session; the year is the start year of the session.
    """
    course_code = session.course.code or "EXAM"
    year = session.starts_at.year
    return f"{course_code}-{year}-{seq:04d}"


@transaction.atomic
def ensure_registrations(session: ExamSession) -> int:
    """Register every active STUDENT user for ``session``.

    Returns the number of *new* rows created. Existing rows are
    left alone — the unique_together makes a second create for the
    same pair a 400, so the service does an explicit check first.

    The function is a no-op (returns 0) if the session has any
    registrations already; the operator can manually delete and
    re-run to repopulate.
    """
    if StudentRegistration.objects.filter(session=session).exists():
        return 0

    students = list(
        User.objects.filter(
            is_active=True,
            user_roles__role__code="STUDENT",
            user_roles__role__is_active=True,
        ).distinct().order_by("email")
    )
    if not students:
        return 0

    rows = []
    for idx, student in enumerate(students, start=1):
        rows.append(
            StudentRegistration(
                session=session,
                student=student,
                student_code=generate_student_code(session, idx),
            )
        )
    StudentRegistration.objects.bulk_create(rows, batch_size=200)
    return len(rows)


__all__ = ["ensure_registrations", "generate_student_code"]

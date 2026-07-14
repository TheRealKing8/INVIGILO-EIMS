"""StudentRegistration — per-(session, student) row, the security officer's
door-scanner target.

A row is the *authoritative* record that "this student is sitting this
paper at this room/this time". The QR code on the student card encodes
the row's id; scanning it at the door resolves the student + session
pair and creates a :class:`apps.attendance.CheckIn` (idempotent on
``(session, user, kind)``).

The ``student_code`` is a short, human-readable label printed on the
card so the student can also type it in by hand if their QR is
unreadable. We don't FK to a separate ``Student`` model — the existing
:class:`apps.accounts.User` with the STUDENT role *is* the student.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class StudentRegistration(BaseModel):
    """A student pre-registered to write a particular exam session.

    One row per ``(session, student)`` pair. The ``unique_together``
    makes a second create for the same pair a 400 — the right signal
    for "already registered" rather than a silent duplicate.
    """

    session = models.ForeignKey(
        "exams.ExamSession",
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exam_registrations",
    )
    student_code = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Short, human-readable code printed on the student card (e.g. CS101-2026-0042).",
    )

    class Meta:
        ordering = ("session__starts_at", "student__email")
        # A student is registered to one session at most once. A
        # second POST for the same pair is a 400, not a duplicate row.
        unique_together = (("session", "student"),)
        indexes = [models.Index(fields=("session", "student"))]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student.email} @ {self.session_id} ({self.student_code})"


__all__ = ["StudentRegistration"]

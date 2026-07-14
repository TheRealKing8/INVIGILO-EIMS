"""Attendance / check-in: who showed up for which exam session.

A :class:`CheckIn` row records one person showing up to one session
once. ``kind`` discriminates the role of the attendee (an invigilator
self check-in vs a student self check-in); ``method`` records the
channel (self-service vs a security officer doing it on someone's
behalf). The same person can be both an invigilator and a student in
different sessions, so uniqueness is scoped to ``(session, user, kind)``.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class CheckIn(BaseModel):
    """A single check-in event for one user at one exam session.

    Append-only — there is no workflow, no edits. The ``late`` flag
    is computed at creation time by :func:`apps.attendance.services.compute_late`
    (10-minute grace window after the session start time) and stored
    on the row so the roster and the CSV export both read it directly
    without re-running the clock comparison.
    """

    class Kind(models.TextChoices):
        INVIGILATOR = "invigilator", "Invigilator"
        STUDENT = "student", "Student"

    class Method(models.TextChoices):
        SELF = "self", "Self"
        BULK = "bulk", "Bulk (security)"

    session = models.ForeignKey(
        "exams.ExamSession",
        on_delete=models.CASCADE,
        related_name="checkins",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="checkins",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)
    method = models.CharField(max_length=16, choices=Method.choices, db_index=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    late = models.BooleanField(default=False)
    location = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Free-text note about where the check-in happened (e.g. 'main door', 'staff entrance').",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkins_recorded",
        help_text="User who created this row. Equal to ``user`` for self check-in; equal to the security officer for bulk check-in.",
    )
    # Base64-encoded PNG of the door e-signature (Phase 15). Empty for
    # self check-ins or for bulk entries where no signature was
    # collected. The payload is small (frontend canvas resizes to
    # ~30-60 KB) so a TextField is enough — no S3 work in this phase.
    signature_image = models.TextField(
        blank=True,
        default="",
        help_text="Base64-encoded PNG of the e-signature captured at the door.",
    )

    class Meta:
        ordering = ("-at",)
        # One check-in per person per session per kind. A second self
        # check-in is a no-op (the view returns the existing row), so
        # we never need to write through this constraint at the view
        # layer.
        unique_together = (("session", "user", "kind"),)
        indexes = [
            models.Index(fields=("session", "kind")),
            models.Index(fields=("user", "-at")),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user_id} @ {self.session_id} ({self.kind})"


__all__ = ["CheckIn"]

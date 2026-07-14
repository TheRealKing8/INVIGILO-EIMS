"""Examination periods and individual exam sessions.

An :class:`ExamPeriod` is a semester or exam-cycle ("Spring 2026", "End
of Sem 2", etc.). An :class:`ExamSession` is one paper in that period:
a Course sitting in a Room at a start/end timestamp. Sessions are the
units the allocation engine reasons about.
"""
from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel


class ExamPeriod(BaseModel):
    """A bounded examination window (semester, midterm, etc.).

    Exactly one period is "active" at a time — the front-end tabs to
    it; the allocation engine runs against it. ``is_active`` is the
    source of truth (a partial unique constraint on ``is_active=True``
    per organisation would be ideal, but we keep it simple here and
    enforce in the service layer).
    """

    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_active = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ("-starts_on", "code")
        indexes = [models.Index(fields=("is_active", "starts_on"))]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} — {self.name}"

    def clean(self) -> None:
        if self.starts_on and self.ends_on and self.starts_on > self.ends_on:
            from django.core.exceptions import ValidationError

            raise ValidationError("starts_on must be on or before ends_on")


class ExamSession(BaseModel):
    """One paper sitting in one room at one moment.

    ``registered`` is the head-count expected to attend; the engine
    uses this to filter rooms. ``status`` is a soft workflow field:
    the engine writes ``draft`` allocations against ``scheduled``
    sessions; a chief invigilator flips them to ``ready`` once
    invigilators are confirmed; the session is then ``in_progress`` on
    exam day and ``completed`` after.
    """

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("ready", "Ready"),
        ("in_progress", "In progress"),
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    period = models.ForeignKey(
        ExamPeriod, on_delete=models.PROTECT, related_name="sessions"
    )
    course = models.ForeignKey(
        "academic.Course", on_delete=models.PROTECT, related_name="exam_sessions"
    )
    # CourseUnit is the leaf of the academic hierarchy
    # (Course → CourseUnit with year + semester). Linking to a unit lets
    # the frontend show the exact offering (Y2/S1) and lets the
    # allocator reason at the unit level. Nullable so existing sessions
    # that pre-date the unit concept still work.
    course_unit = models.ForeignKey(
        "academic.CourseUnit",
        on_delete=models.PROTECT,
        related_name="exam_sessions",
        null=True,
        blank=True,
    )
    room = models.ForeignKey(
        "rooms.Room", on_delete=models.PROTECT, related_name="exam_sessions", null=True, blank=True
    )
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField()
    registered = models.PositiveIntegerField(default=0)
    invigilators_required = models.PositiveSmallIntegerField(default=2)
    status = models.CharField(
        max_length=24, choices=STATUS_CHOICES, default="scheduled", db_index=True
    )
    special_requirements = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Free-text notes about special arrangements (e.g. large-print "
            "papers, extra time, separate venue, specific equipment)."
        ),
    )

    class Meta:
        ordering = ("starts_at", "course__code")
        indexes = [
            models.Index(fields=("period", "status")),
            models.Index(fields=("starts_at", "ends_at")),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.course.code} @ {self.starts_at:%Y-%m-%d %H:%M}"

    def clean(self) -> None:
        if self.starts_at and self.ends_at and self.starts_at >= self.ends_at:
            from django.core.exceptions import ValidationError

            raise ValidationError("starts_at must be earlier than ends_at")
        if self.room_id and self.capacity > self.room.capacity:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                {"capacity": f"capacity {self.capacity} exceeds room capacity {self.room.capacity}"}
            )


__all__ = ["ExamPeriod", "ExamSession", "StudentRegistration"]

# Re-export StudentRegistration so Django's model discovery (which
# walks ``models.py``) finds the table. The canonical class lives in
# ``apps.exams.student_registration`` to keep this file focused on
# ExamPeriod / ExamSession.
from .student_registration import StudentRegistration  # noqa: E402,F401

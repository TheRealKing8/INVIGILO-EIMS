"""Allocations: a many-to-many between ExamSession, Invigilator, and Room.

The :class:`Allocation` row records one invigilator assigned to one
session in one room, with a status (draft/confirmed/rejected). Each
:class:`AllocationRun` records one execution of the engine: which
sessions were placed, which weren't, and a summary.

We use explicit ``Allocation`` rows (rather than a M2M through table)
because the allocation itself has business state — a chief invigilator
confirms or rejects, a run can be rolled back, and the audit log needs
to see the row.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class AllocationRun(BaseModel):
    """A single execution of the allocation engine.

    Created by ``POST /api/v1/allocations/run/``. Stores the constraint
    settings used, summary stats, and the actor who triggered it.
    """

    period = models.ForeignKey(
        "exams.ExamPeriod", on_delete=models.PROTECT, related_name="allocation_runs"
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="allocation_runs",
    )
    sessions_total = models.PositiveIntegerField(default=0)
    sessions_placed = models.PositiveIntegerField(default=0)
    avg_workload = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_workload = models.PositiveSmallIntegerField(default=0)
    capacity_utilisation = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    runtime_seconds = models.PositiveIntegerField(default=0)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("period", "-created_at"))]


class Allocation(BaseModel):
    """One invigilator assigned to one session in one room.

    A session with N invigilators has N rows here.
    """

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("rejected", "Rejected"),
    )

    run = models.ForeignKey(
        AllocationRun, on_delete=models.CASCADE, related_name="allocations"
    )
    session = models.ForeignKey(
        "exams.ExamSession", on_delete=models.CASCADE, related_name="allocations"
    )
    invigilator = models.ForeignKey(
        "invigilators.InvigilatorProfile",
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    room = models.ForeignKey(
        "rooms.Room", on_delete=models.PROTECT, related_name="allocations", null=True, blank=True
    )
    role = models.CharField(
        max_length=32, default="invigilator",
        help_text="Free-text: 'chief', 'invigilator', 'reserve', etc.",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="draft", db_index=True
    )

    class Meta:
        ordering = ("session__starts_at", "invigilator__user__full_name")
        indexes = [
            models.Index(fields=("session", "status")),
            models.Index(fields=("invigilator", "status")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("session", "invigilator"),
                name="allocations_unique_session_invigilator",
            ),
        ]


class Conflict(BaseModel):
    """A constraint the engine couldn't satisfy.

    Attached to a :class:`AllocationRun` so the UI can show "1 conflict
    to review" and the chief can drill in.
    """

    SEVERITY_CHOICES = (
        ("warning", "Warning"),
        ("error", "Error"),
    )

    TYPE_CHOICES = (
        ("double_booking", "Invigilator double-booked"),
        ("dept_mix", "Department-mix violation"),
        ("no_eligible_invigilators", "No eligible invigilators"),
        ("no_room_capacity", "No room with enough capacity"),
        ("workload_cap", "Workload cap exceeded"),
        ("unavailability", "Invigilator unavailable"),
    )

    run = models.ForeignKey(
        AllocationRun, on_delete=models.CASCADE, related_name="conflicts"
    )
    session = models.ForeignKey(
        "exams.ExamSession",
        on_delete=models.CASCADE,
        related_name="conflicts",
        null=True,
        blank=True,
    )
    invigilator = models.ForeignKey(
        "invigilators.InvigilatorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conflicts",
    )
    type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="error")
    detail = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("run", "type"))]


__all__ = ["Allocation", "AllocationRun", "Conflict"]

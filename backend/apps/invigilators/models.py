"""Invigilator profiles and per-day availability.

An :class:`InvigilatorProfile` is a 1:1 attachment to a ``User`` (the
auth user is the source of truth; the profile adds business fields
like max-sessions-per-cycle, rating, and the home department used for
dept-mixing rules).

:class:`Availability` is a per-date override: the default is "available"
(no row), and a row expresses "off_duty" or "leave" or "busy" for a
single date. The allocation engine filters candidates by combining
``profile.is_active``, ``profile.user.is_active``, and any matching
``Availability`` row for the session's date.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class InvigilatorProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invigilator_profile",
    )
    primary_department = models.ForeignKey(
        "academic.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invigilators",
    )
    max_sessions_per_cycle = models.PositiveSmallIntegerField(default=6)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=4.50)

    class Meta:
        ordering = ("user__full_name",)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user.full_name} ({self.primary_department_id or 'no dept'})"


class Availability(BaseModel):
    """A per-date status override for an invigilator.

    No row == available. A row expresses "off_duty", "leave", or "busy"
    for a particular date.
    """

    STATUS_CHOICES = (
        ("available", "Available"),
        ("busy", "Busy"),
        ("off_duty", "Off duty"),
        ("leave", "On leave"),
    )

    invigilator = models.ForeignKey(
        InvigilatorProfile, on_delete=models.CASCADE, related_name="availability"
    )
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="available")
    note = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        unique_together = (("invigilator", "date"),)
        ordering = ("date",)
        indexes = [models.Index(fields=("date", "status"))]


__all__ = ["InvigilatorProfile", "Availability"]

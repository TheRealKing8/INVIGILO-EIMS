"""Incidents: anything that disrupted or could have disrupted an exam.

Reported by the invigilator on the day, escalated to the chief, then
to the exam officer. Status is the workflow state; severity is the
blast radius.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Incident(BaseModel):
    SEVERITY_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    )

    STATUS_CHOICES = (
        ("open", "Open"),
        ("investigating", "Investigating"),
        ("escalated", "Escalated"),
        ("resolved", "Resolved"),
    )

    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    session = models.ForeignKey(
        "exams.ExamSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="incidents_reported",
    )
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="medium", db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="open", db_index=True)
    reported_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents_resolved",
    )

    class Meta:
        ordering = ("-reported_at",)
        indexes = [
            models.Index(fields=("status", "-reported_at")),
            models.Index(fields=("severity", "status")),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"INC-{self.id} {self.title}"


__all__ = ["Incident"]

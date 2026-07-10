"""Report exports: a row per generated file with a download endpoint."""
from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


def _report_upload_path(instance: "ReportExport", filename: str) -> str:
    """Place every export in ``media/reports/<cycle_code>/<id>.<ext>``."""
    ext = Path(filename).suffix or ""
    folder = instance.cycle.code if instance.cycle_id else "ad-hoc"
    return f"reports/{folder}/{instance.id}{ext}"


class ReportExport(BaseModel):
    FORMAT_CHOICES = (
        ("pdf", "PDF"),
        ("excel", "Excel"),
        ("csv", "CSV"),
    )

    AUDIENCE_CHOICES = (
        ("internal", "Internal"),
        ("registrar", "Registrar"),
        ("senate", "Senate"),
        ("public", "Public"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    format = models.CharField(max_length=8, choices=FORMAT_CHOICES)
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES, default="internal")
    cycle = models.ForeignKey(
        "exams.ExamPeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_exports",
    )
    file = models.FileField(upload_to=_report_upload_path, null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="report_exports",
    )
    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    parameters = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-generated_at",)
        indexes = [models.Index(fields=("format", "-generated_at"))]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.title} ({self.format})"


__all__ = ["ReportExport"]

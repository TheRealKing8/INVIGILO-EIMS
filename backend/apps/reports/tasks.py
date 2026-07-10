"""Celery tasks for asynchronous report generation.

In test mode ``CELERY_TASK_ALWAYS_EAGER=True`` so ``.apply()`` runs
inline; in production the worker picks up the queued task.
"""
from __future__ import annotations

import io
import logging
from typing import Iterable

from celery import shared_task
from django.core.files.base import ContentFile

from .models import ReportExport

logger = logging.getLogger("invigilo.reports")


def _render_export(export: ReportExport) -> bytes:
    """Dispatch to the right renderer for ``export.format``.

    Falls back to a short text body when the model/format combination
    is unknown so the file is never empty (the ``ReportExport`` row
    always has a downloadable artifact).
    """
    fmt = export.format
    if fmt == "pdf":
        from .services.pdf import render_attendance_summary

        cycle = export.cycle
        if cycle is None:
            return _placeholder(export, reason="no cycle attached")
        return render_attendance_summary(cycle)
    if fmt == "excel":
        from .services.excel import render_workbook

        cycle = export.cycle
        if cycle is None:
            return _placeholder(export, reason="no cycle attached")
        return render_workbook(cycle)
    if fmt == "csv":
        from .services.csv import render_csv

        model_name = (export.parameters or {}).get("model", "incidents")
        return render_csv(model_name)
    return _placeholder(export, reason=f"unknown format {fmt!r}")


def _placeholder(export: ReportExport, *, reason: str) -> bytes:
    body = (
        f"# {export.title}\n"
        f"Format: {export.format}\n"
        f"Audience: {export.audience}\n"
        f"Reason for placeholder: {reason}\n"
        f"Generated: {export.generated_at.isoformat() if export.generated_at else 'pending'}\n"
    ).encode("utf-8")
    return body


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600)
def generate_report(self, export_id: str) -> str:  # type: ignore[no-untyped-def]
    """Render the export's file and attach it to the row."""
    try:
        export = ReportExport.objects.get(pk=export_id)
    except ReportExport.DoesNotExist:
        logger.warning("ReportExport %s missing when generate_report ran", export_id)
        return "missing"
    body = _render_export(export)
    ext = {"pdf": "pdf", "excel": "xlsx", "csv": "csv"}[export.format]
    export.file.save(
        f"{export.id}.{ext}",
        ContentFile(body),
        save=True,
    )
    return "ok"


__all__ = ["generate_report"]

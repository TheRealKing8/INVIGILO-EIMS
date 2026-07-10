"""PDF report renderers using reportlab.

Each function returns raw PDF bytes. The bytes are handed to Django's
``ContentFile`` and stored in the ``ReportExport.file`` FileField.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.allocations.models import Allocation
from apps.exams.models import ExamSession
from apps.invigilators.models import InvigilatorProfile


def _doc(buffer: io.BytesIO, title: str) -> SimpleDocTemplate:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=title,
    )
    doc._invigilo_title = title  # for the header
    return doc


def render_attendance_summary(
    period, sessions: Iterable[ExamSession] | None = None
) -> bytes:
    """One-page summary of every session in the period with seat-fill %."""
    buffer = io.BytesIO()
    doc = _doc(buffer, f"Attendance Summary — {period.code}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>{period.name}</b>", styles["Title"]),
        Paragraph(
            f"{period.starts_on:%Y-%m-%d} to {period.ends_on:%Y-%m-%d}",
            styles["Normal"],
        ),
        Spacer(1, 0.5 * cm),
    ]

    qs = (
        sessions
        if sessions is not None
        else ExamSession.objects.filter(period=period).select_related("course", "room")
    )
    rows: list[list] = [["Date", "Course", "Room", "Registered", "Capacity", "Fill %"]]
    for s in qs:
        fill = round((s.registered / s.capacity) * 100, 1) if s.capacity else 0
        rows.append(
            [
                s.starts_at.strftime("%Y-%m-%d %H:%M"),
                s.course.code,
                s.room.code if s.room else "—",
                str(s.registered),
                str(s.capacity),
                f"{fill}%",
            ]
        )
    table = Table(rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def render_workload_report(
    department, profiles: Iterable[InvigilatorProfile] | None = None
) -> bytes:
    """One-page workload breakdown by invigilator within a department."""
    buffer = io.BytesIO()
    doc = _doc(buffer, f"Workload — {department.code}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>{department.name}</b>", styles["Title"]),
        Spacer(1, 0.5 * cm),
    ]

    qs = (
        profiles
        if profiles is not None
        else InvigilatorProfile.objects.filter(primary_department=department)
        .select_related("user")
    )
    rows: list[list] = [["Invigilator", "Email", "Max / cycle", "Allocated"]]
    for p in qs:
        allocated = Allocation.objects.filter(
            invigilator=p, run__period__is_active=True
        ).count()
        rows.append([p.user.full_name, p.user.email, str(p.max_sessions_per_cycle), str(allocated)])
    table = Table(rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


__all__ = ["render_attendance_summary", "render_workload_report"]

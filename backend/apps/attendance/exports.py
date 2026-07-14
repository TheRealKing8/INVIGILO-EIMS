"""CSV export view for attendance.

Mounted as a function-based view rather than a viewset action so
the URL can carry a literal ``.csv`` suffix without fighting
DRF's format-suffix router.
"""
from __future__ import annotations

import csv
from io import StringIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import (
    api_view,
    permission_classes,
)

from apps.core.permissions import HasPermission
from apps.exams.models import ExamSession

from .services import build_roster, csv_safe


@api_view(["GET"])
@permission_classes([HasPermission.with_codes("attendance.view")])
def export_session_csv(request, session_id):  # type: ignore[no-untyped-def]
    """Download the roster for one session as a CSV attachment.

    The first column identifies the row kind so the same file
    can carry both invigilator and student rows without an
    extra header.
    """
    session = get_object_or_404(ExamSession, id=session_id)
    roster = build_roster(session)
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "kind",
            "user_id",
            "email",
            "full_name",
            "present",
            "late",
            "at",
            "method",
            "location",
            "recorded_by_email",
        ]
    )
    for row in roster["invigilators"]:
        writer.writerow(
            [
                csv_safe("invigilator"),
                csv_safe(row["user_id"]),
                csv_safe(row["email"]),
                csv_safe(row["full_name"]),
                csv_safe(row["present"]),
                csv_safe(row["late"]),
                csv_safe(row["at"].isoformat() if row["at"] else ""),
                csv_safe(row["method"]),
                csv_safe(row["location"]),
                csv_safe(row["recorded_by_email"]),
            ]
        )
    for row in roster["students"]:
        writer.writerow(
            [
                csv_safe("student"),
                csv_safe(row["user_id"]),
                csv_safe(row["email"]),
                csv_safe(row["full_name"]),
                csv_safe(True),
                csv_safe(row["late"]),
                csv_safe(row["at"].isoformat() if row["at"] else ""),
                csv_safe(row["method"]),
                csv_safe(row["location"]),
                csv_safe(row["recorded_by_email"]),
            ]
        )
    response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    filename = f"attendance-{session.course.code}-{session.id}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


__all__ = ["export_session_csv"]

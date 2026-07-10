"""CSV report renderers (stdlib only)."""
from __future__ import annotations

import csv
import io
from typing import Iterable

from apps.allocations.models import Allocation
from apps.incidents.models import Incident


def render_csv(model_name: str, queryset: Iterable | None = None) -> bytes:
    """Render a CSV of the named model.

    The ``queryset`` argument is optional; when omitted we resolve the
    default queryset for the named model.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if model_name == "incidents":
        if queryset is None:
            queryset = Incident.objects.select_related("session__course", "reporter")
        writer.writerow(["id", "title", "severity", "status", "session", "reporter", "reported_at"])
        for i in queryset:
            writer.writerow(
                [
                    str(i.id),
                    i.title,
                    i.severity,
                    i.status,
                    i.session.course.code if i.session else "",
                    i.reporter.email if i.reporter else "",
                    i.reported_at.isoformat() if i.reported_at else "",
                ]
            )
    elif model_name == "allocations":
        if queryset is None:
            queryset = Allocation.objects.select_related("session__course", "invigilator__user", "room")
        writer.writerow(["id", "course", "starts_at", "invigilator", "role", "status", "room"])
        for a in queryset:
            writer.writerow(
                [
                    str(a.id),
                    a.session.course.code,
                    a.session.starts_at.isoformat(),
                    a.invigilator.user.full_name,
                    a.role,
                    a.status,
                    a.room.code if a.room else "",
                ]
            )
    else:
        # Unknown model — emit a placeholder row so the file is non-empty.
        writer.writerow(["model", "value"])
        writer.writerow([model_name, "unknown — no renderer registered"])

    return buffer.getvalue().encode("utf-8")


__all__ = ["render_csv"]

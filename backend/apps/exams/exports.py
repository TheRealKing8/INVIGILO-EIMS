"""Timetable .ics export.

Mounted as a function-based view rather than a viewset action so
the URL can carry a literal ``.ics`` suffix without fighting
DRF's format-suffix router (same pattern as the attendance CSV
export in Phase 13 and the per-session .ics export in Phase 14).

Unlike ``apps.notifications.calendar.calendar_feed`` (which is
*user-scoped* via ``upcoming_sessions_for``), this endpoint
returns the **timetable itself** — what the operations team
sees on ``/dashboard/timetable`` — not "my personal calendar".
The two endpoints serve different mental models:

* ``GET /api/v1/calendar/feed.ics`` — "what sessions are on
  *my* calendar" (role-scoped: invigilators see their
  allocations, students see public upcoming, ops see all).
* ``GET /api/v1/exams/timetable.ics`` — "the *whole*
  timetable, optionally filtered" (operations view; every
  authenticated user with the right perms sees the same data).
"""
from __future__ import annotations

from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.notifications.services import build_ics


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def timetable_ics(request):  # type: ignore[no-untyped-def]
    """Return the timetable (filtered by ``?range=`` and/or ``?period=``) as an .ics feed.

    Query params (both optional):

    * ``range=today|week|next_week|all`` — default ``week``,
      matches the timetable page's default chip.
    * ``period=<uuid>`` — restrict to a single exam period.

    Auth is via the project's default JWT cookie (the
    ``JWTAuthentication`` in ``REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]``).
    Most calendar clients can't carry cookies, so the intended
    workflow is *download* the file via the frontend's
    ``<a download href="...">`` link and import it manually
    into Outlook/Apple Calendar/Google Calendar.
    """
    from apps.exams.models import ExamSession  # local to avoid cycle

    qs = (
        ExamSession.objects
        .select_related("course", "room", "room__building", "period")
        .exclude(status="cancelled")
        .order_by("starts_at")
    )

    period_id = request.query_params.get("period")
    if period_id:
        qs = qs.filter(period_id=period_id)

    range_ = request.query_params.get("range", "week")
    if range_ != "all":
        now = timezone.now()
        if range_ == "today":
            qs = qs.filter(starts_at__date=now.date())
        elif range_ == "next_week":
            start = now + timedelta(days=7)
            end = start + timedelta(days=7)
            qs = qs.filter(starts_at__gte=start, starts_at__lt=end)
        else:  # "week" (default)
            end = now + timedelta(days=7)
            qs = qs.filter(starts_at__gte=now, starts_at__lt=end)

    body = build_ics(list(qs), calendar_name="INVIGILO — Timetable")
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="invigilo-timetable.ics"'
    return response


__all__ = ["timetable_ics"]

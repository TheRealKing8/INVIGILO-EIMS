"""Calendar (.ics) export.

End-points:

* ``GET /api/v1/calendar/feed.ics`` — the user's upcoming sessions
  as an iCalendar (RFC 5545) feed. Any calendar app that supports
  HTTP-downloaded feeds (Outlook, Apple Calendar, Google Calendar
  via URL import) can subscribe.

* ``GET /api/v1/calendar/sessions/{id}.ics`` — a single session
  as a one-event .ics. Used by the "Download this session" button
  on ``/dashboard/exams/[id]``. The whole-feed URL is unchanged.

The function views are mounted directly in :mod:`apps.notifications.urls_calendar`
so the literal ``feed.ics`` and ``sessions/{id}.ics`` suffixes don't
fight DRF's format-suffix router (same pattern as the attendance
CSV export in Phase 13).
"""
from __future__ import annotations

from django.http import Http404, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .services import build_ics, upcoming_sessions_for


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def calendar_feed(request):  # type: ignore[no-untyped-def]
    """Return the requesting user's upcoming sessions as an .ics feed.

    Auth is via the project's default JWT cookie (set by the
    ``JWTAuthentication`` in ``REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]``).
    Most calendar clients that pull via URL can't carry cookies, so the
    intended workflow is *download* the file (the frontend uses an
    ``<a download href="...">`` link) and import it manually.
    """
    user = request.user
    sessions = list(upcoming_sessions_for(user))
    body = build_ics(sessions, calendar_name=f"INVIGILO — {user.full_name}")
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="invigilo-calendar.ics"'
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_calendar(request, session_id):  # type: ignore[no-untyped-def]
    """Return a single :class:`ExamSession` as a one-event .ics.

    Authorisation mirrors the existing feed's data scope:

    * Operations roles (SA / EO / HoD / Dean / SecOps) — any session.
    * INVIGILATOR — only sessions they have a confirmed allocation to.
    * STUDENT — only sessions they have a :class:`StudentRegistration`
      for (Phase 15). Falls back to the public upcoming list when
      the student has no explicit registration (matches
      :func:`apps.notifications.services.upcoming_sessions_for`).

    404 covers both "no such session" and "no access" so we don't
    leak the existence of an out-of-scope row.
    """
    from apps.exams.models import ExamSession
    from apps.allocations.models import Allocation
    from apps.exams.student_registration import StudentRegistration

    try:
        session = ExamSession.objects.select_related("course", "room", "room__building").get(pk=session_id)
    except (ExamSession.DoesNotExist, ValueError):
        raise Http404("Session not found.")

    user = request.user
    is_staff_or_ops = (
        user.is_superuser
        or user.is_staff
        or user.has_role("SYSTEM_ADMINISTRATOR")
        or user.has_role("EXAMINATION_OFFICER")
        or user.has_role("HEAD_OF_DEPARTMENT")
        or user.has_role("FACULTY_DEAN")
        or user.has_role("SECURITY_OFFICER")
    )
    allowed = is_staff_or_ops
    if not allowed and user.has_role("INVIGILATOR"):
        allowed = Allocation.objects.filter(
            session=session,
            invigilator__user=user,
            status="confirmed",
        ).exists()
    if not allowed and user.has_role("STUDENT"):
        # Phase 15 introduced StudentRegistration; if a row exists
        # the student is "on the list" for this session. The
        # fallback below lets any student import a public-upcoming
        # session (the historic behaviour, mirrors
        # :func:`upcoming_sessions_for`).
        allowed = StudentRegistration.objects.filter(
            session=session, student=user
        ).exists()
    if not allowed and user.has_role("STUDENT"):
        from django.utils import timezone
        if session.starts_at >= timezone.now():
            allowed = True
    if not allowed:
        raise Http404("Session not found.")

    body = build_ics([session], calendar_name=f"INVIGILO — {session.course.code}")
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="invigilo-{session.course.code}-{session.id}.ics"'
    )
    return response


__all__ = ["calendar_feed", "session_calendar"]

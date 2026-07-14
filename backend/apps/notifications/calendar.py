"""Calendar (.ics) export.

End-point:

* ``GET /api/v1/calendar/feed.ics`` — the user's upcoming sessions
  as an iCalendar (RFC 5545) feed. Any calendar app that supports
  HTTP-downloaded feeds (Outlook, Apple Calendar, Google Calendar
  via URL import) can subscribe.

The function view is mounted directly in :mod:`apps.notifications.urls`
so the literal ``feed.ics`` suffix doesn't fight DRF's format-suffix
router (same pattern as the attendance CSV export in Phase 13).
"""
from __future__ import annotations

from django.http import HttpResponse
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


__all__ = ["calendar_feed"]

"""URL configuration for the realtime SSE module (Phase 20).

Three endpoints, all mounted under ``/api/v1/realtime/``:

  * ``GET  notifications/stream/``  — per-user bell wakeups.
  * ``GET  attendance/sessions/<uuid>/stream/``  — per-session live feed.
  * ``POST ai/chat/stream/``  — streaming LLM reply.

Why no throttling on the GET streams
------------------------------------
DRF throttles the *request*, not the *connection*. The consumer
holds a single open connection for 5 minutes (then we close it
and the browser reconnects). If we throttled at the connect
rate, a user opening the dashboard during a busy period would
get 429s even though they only have one open stream. Throttle
the AI stream instead — that's the path that actually costs
us money (LLM calls).

No ``schema="realtime"`` prefix concern here either — drf-spectacular
emits an OpenAPI block for each view regardless of the URL prefix.
"""
from __future__ import annotations

from django.urls import path

from . import views

app_name = "realtime"

urlpatterns = [
    path(
        "notifications/stream/",
        views.NotificationsStreamView.as_view(),
        name="notifications-stream",
    ),
    path(
        "attendance/sessions/<uuid:session_id>/stream/",
        views.AttendanceSessionStreamView.as_view(),
        name="attendance-session-stream",
    ),
    path(
        "ai/chat/stream/",
        views.AIChatStreamView.as_view(),
        name="ai-chat-stream",
    ),
]


__all__ = ["urlpatterns"]

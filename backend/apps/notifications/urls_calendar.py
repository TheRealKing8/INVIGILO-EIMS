"""URL config for the calendar feed (mounted at ``/api/v1/calendar/``).

Separated from :mod:`apps.notifications.urls` so the calendar URL
lives under its own namespace (``/api/v1/calendar/feed.ics``) rather
than nested inside the notifications resource.
"""
from __future__ import annotations

from django.urls import path

from .calendar import calendar_feed

urlpatterns = [
    path("feed.ics", calendar_feed, name="calendar-feed"),
]


__all__ = ["urlpatterns"]

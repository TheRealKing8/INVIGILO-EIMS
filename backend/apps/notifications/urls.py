"""URL config for the notifications app.

Mounted in :mod:`invigilo.urls` under ``/api/v1/notifications/``.
The calendar feed is mounted separately in :mod:`invigilo.urls` at
``/api/v1/calendar/feed.ics`` so it doesn't live under a
``/notifications/`` URL segment.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet

router = DefaultRouter(trailing_slash=True)
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
]


__all__ = ["urlpatterns"]

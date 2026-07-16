"""App config for the realtime SSE module (Phase 20).

The :class:`RealtimeConfig.ready` hook imports the signal handlers in
:mod:`apps.realtime.hooks` so the post-save on :class:`Notification`
and :class:`CheckIn` fires the in-process pub/sub. The pub/sub is the
wakeup channel for SSE consumers; the actual data is always fetched
fresh from the DB.
"""
from __future__ import annotations

from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.realtime"
    label = "realtime"
    verbose_name = "Realtime"

    def ready(self) -> None:  # pragma: no cover
        # Imported for side-effects (signal registration).
        from . import hooks  # noqa: F401


__all__ = ["RealtimeConfig"]

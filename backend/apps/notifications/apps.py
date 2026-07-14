"""App config for the notifications module.

The :class:`NotificationsConfig.ready` hook imports the signal handlers
so the post-save on :class:`apps.allocations.models.Allocation` fires
the :func:`apps.notifications.services.notify` call. We import inside
``ready`` to avoid the circular-import trap: ``signals`` imports the
``Allocation`` model, and the ``Allocation`` model is registered with
Django by the time ``ready`` runs.
"""
from __future__ import annotations

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notifications"

    def ready(self) -> None:  # pragma: no cover
        # Imported for side-effects (signal registration).
        from . import signals  # noqa: F401


__all__ = ["NotificationsConfig"]

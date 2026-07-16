"""Signal handlers that wake SSE consumers (Phase 20).

Two receivers:

* :func:`notification_saved` — fires whenever a ``Notification`` row
  is created or has its ``read_at`` flipped. The wakeup is per-recipient
  (channel ``user:<id>``).
* :func:`checkin_saved` — fires whenever a ``CheckIn`` row is created
  or updated. The wakeup is per-session (channel ``session:<uuid>``).

The receivers do *not* push the new value to the consumer — the
consumer re-reads from the DB. The wakeup is just a "something
changed, please re-fetch" hint. This keeps the in-process pubsub
simple (no payload serialisation) and means a cross-process event
that misses the wakeup is at most 30s stale, not lost.

Wired by :class:`apps.realtime.apps.RealtimeConfig.ready`.
"""
from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from .pubsub import channel_for_session, channel_for_user, publish

logger = logging.getLogger("invigilo.realtime.hooks")


@receiver(post_save, sender="notifications.Notification")
def notification_saved(sender: Any, instance: Any, **kwargs: Any) -> None:
    """Wake the recipient's bell stream.

    Fires on create (new notification → unread count goes up) AND
    on update (mark-read → unread count goes down). Both matter
    to the UI.
    """
    recipient_id = getattr(instance, "recipient_id", None)
    if recipient_id is None:
        return
    publish(channel_for_user(recipient_id), event="unread_count")


@receiver(post_save, sender="attendance.CheckIn")
def checkin_saved(sender: Any, instance: Any, **kwargs: Any) -> None:
    """Wake the session's live-feed stream.

    Fires on the *first* scan (create) and on the no-op duplicate
    (update) — both are valid wake-up signals because the live
    feed's view of "last 20" depends on ``at`` ordering. We only
    skip the signal if the row has no ``session_id`` (shouldn't
    happen but defensive).
    """
    session_id = getattr(instance, "session_id", None)
    if session_id is None:
        return
    publish(channel_for_session(session_id), event="checkin")


__all__ = ["notification_saved", "checkin_saved"]

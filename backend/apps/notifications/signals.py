"""Signal handlers that fire notifications on model changes.

Wired by :class:`apps.notifications.apps.NotificationsConfig.ready`.

Only one handler today — :func:`allocation_created_or_changed` — and
its scope is narrow: it fires for *new* confirmed allocations and for
*reassignments* (where ``update_fields`` includes ``invigilator``).
The "old invigilator" half of a reassign is handled directly in the
view (``AllocationViewSet.reassign``) so we have access to the FK
before it's overwritten.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import notify

logger = logging.getLogger("invigilo.notifications.signals")


def _fmt_when(value: Any) -> str:
    """Render a ``starts_at`` value as a human-readable timestamp.

    The field is a ``DateTimeField`` but some test fixtures pass a
    string. Render as ISO-8601 (or the raw string) so we never
    crash a save with a bad format specifier.
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


@receiver(post_save, sender="allocations.Allocation")
def allocation_created_or_changed(
    sender: Any, instance: Any, created: bool, update_fields: Any = None, **kwargs: Any
) -> None:
    """Fire a notification for the *recipient* invigilator.

    * On ``created=True`` with ``status="confirmed"`` → "allocation.new".
    * On a save with ``update_fields`` containing ``invigilator`` →
      "allocation.reassigned" (the new invigilator is ``instance.invigilator``).
    """
    if instance.status != "confirmed":
        return
    try:
        user = instance.invigilator.user
    except AttributeError:
        # The FK chain is broken (invigilator or user was deleted
        # mid-save). Skip — there's no one to notify.
        logger.warning("allocation_created_or_changed: broken invigilator FK on %s", instance.id)
        return

    target_type = "Allocation"
    target_id = str(instance.id)
    when = _fmt_when(instance.session.starts_at)
    course_code = instance.session.course.code
    room_code = instance.room.code if instance.room else "TBA"

    if created:
        notify(
            recipient=user,
            kind="allocation.new",
            title=f"New assignment: {course_code}",
            body=(
                f"You've been assigned to {course_code} on {when} in {room_code}."
            ),
            target_type=target_type,
            target_id=target_id,
        )
        return

    if update_fields and "invigilator" in update_fields:
        notify(
            recipient=user,
            kind="allocation.reassigned",
            title=f"Reassigned to {course_code}",
            body=f"You've been reassigned to {course_code} on {when}.",
            target_type=target_type,
            target_id=target_id,
        )


__all__ = ["allocation_created_or_changed"]

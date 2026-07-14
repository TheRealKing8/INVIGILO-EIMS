"""Notification model — the in-app event feed.

One row per (recipient, event) pair. The feed page reads by recipient;
the topbar bell reads by recipient + is_read.

The event is identified polymorphically by ``(target_type, target_id)``
so a single notification can link to an allocation, an incident, a
session, etc. without us maintaining an FK per app.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Notification(BaseModel):
    """An in-app event delivered to a single user.

    Created by the service layer (:func:`apps.notifications.services.notify`)
    from a trigger in another app (allocation engine, reassign action,
    incident status change). Read by the user's notification feed.

    Delivery state:
        * ``is_read`` + ``read_at`` — set by the user's "mark read" action
        * ``email_sent_at`` — set by the Celery task after SMTP success
        * ``email_failed`` — set on SMTP failure; the task will not retry
    """

    class Kind(models.TextChoices):
        ALLOCATION_REASSIGNED = "allocation.reassigned", "You were reassigned"
        ALLOCATION_NEW = "allocation.new", "You were assigned"
        INCIDENT_ESCALATED = "incident.escalated", "Incident escalated to you"
        INCIDENT_RESOLVED = "incident.resolved", "Incident resolved"
        SESSION_RESCHEDULED = "session.rescheduled", "Session rescheduled"
        SESSION_CANCELLED = "session.cancelled", "Session cancelled"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=64, choices=Kind.choices, db_index=True)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    target_type = models.CharField(max_length=64, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_failed = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("recipient", "-created_at")),
            models.Index(fields=("recipient", "is_read", "-created_at")),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.recipient_id} · {self.kind} · {self.title!r}"


__all__ = ["Notification"]

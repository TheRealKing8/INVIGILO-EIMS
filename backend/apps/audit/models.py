"""Append-only audit log.

A single ``AuditLog`` row records every consequential write. The
:func:`apps.core.audit.get_actor` helper reads the request's audit
context to attach the actor without views having to thread it through.

Wired by ``apps.audit.signals`` (added in Phase 5; this phase just
provides the table so the rest of the system can FK it).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class AuditLog(BaseModel):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, db_index=True)
    target_id = models.CharField(max_length=64, db_index=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    path = models.CharField(max_length=512, blank=True, default="")
    method = models.CharField(max_length=8, blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("target_type", "target_id", "-created_at")),
            models.Index(fields=("actor", "-created_at")),
        ]


__all__ = ["AuditLog"]

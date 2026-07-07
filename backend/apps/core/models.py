"""Base model classes used by every business app.

The classes are designed to be mixed-and-matched. The "kitchen sink"
base (``BaseModel``) bundles the three concerns most entities have:
a UUID primary key, timestamps, and a soft-delete flag.
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.core.managers import SoftDeleteManager


class UUIDModel(models.Model):
    """Replace the default integer PK with a UUIDv4.

    UUIDs prevent enumeration attacks (no row-count leak) and let the
    frontend generate row references before persistence.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """Add ``created_at`` and ``updated_at`` columns.

    ``updated_at`` is touched automatically by ``Model.save``.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)


class SoftDeleteModel(models.Model):
    """Add an ``is_active`` boolean that hides rows from default queries.

    The companion manager :class:`SoftDeleteManager` filters
    ``is_active=True`` by default. The base :class:`models.Manager` is
    preserved on the instance as ``all_objects`` for hard lookups (e.g.
    restore flows, audit work).
    """

    is_active = models.BooleanField(default=True, db_index=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    # The default manager for a soft-delete-aware model: hides deactivated
    # rows. Override with ``Meta.base_manager_name = "all_objects"`` for
    # related-object lookups that must see every row.
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        base_manager_name = "all_objects"

    def soft_delete(self) -> None:
        from django.utils import timezone

        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=("is_active", "deactivated_at", "updated_at"))


class BaseModel(UUIDModel, TimestampedModel, SoftDeleteModel):
    """The standard base for any non-trivial model in the system.

    Inherits:
        * UUID primary key (``UUIDModel``)
        * ``created_at`` / ``updated_at`` (``TimestampedModel``)
        * ``is_active`` / ``deactivated_at`` (``SoftDeleteModel``)
    """

    class Meta:
        abstract = True


__all__ = ["BaseModel", "SoftDeleteModel", "TimestampedModel", "UUIDModel"]

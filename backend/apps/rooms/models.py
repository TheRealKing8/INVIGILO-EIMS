"""Rooms and the buildings that contain them."""
from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel


class Building(BaseModel):
    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} — {self.name}"


class Room(BaseModel):
    """A physical seatable space, e.g. ``Room A3`` or ``Lab 4``.

    ``capacity`` is the head-count limit imposed by the space (rows of
    seats + walkways). ``equipment`` is a free-text blob describing
    things like "projector, 40 PCs, accessibility ramp". The allocation
    engine only filters on ``capacity``; equipment is for the front-end
    to display.
    """

    building = models.ForeignKey(
        Building, on_delete=models.PROTECT, related_name="rooms"
    )
    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=128, blank=True, default="")
    capacity = models.PositiveIntegerField()
    equipment = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("building__code", "code")
        indexes = [models.Index(fields=("building", "code"))]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.building.code}/{self.code}"


__all__ = ["Building", "Room"]

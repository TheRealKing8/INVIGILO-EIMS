"""Custom managers for the abstract models in :mod:`apps.core.models`."""
from __future__ import annotations

from typing import Any

from django.db import models


class SoftDeleteManager(models.Manager):
    """A manager that hides soft-deleted rows by default.

    Use ``MyModel.all_objects`` to bypass the filter.
    """

    def get_queryset(self) -> models.QuerySet:  # type: ignore[type-arg]
        return super().get_queryset().filter(is_active=True)


__all__ = ["SoftDeleteManager"]

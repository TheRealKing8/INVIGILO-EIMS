"""Common filter sets shared by the business apps."""
from __future__ import annotations

import django_filters


class IsActiveFilter(django_filters.BooleanFilter):
    """A boolean filter that defaults to true.

    Clients can pass ``?is_active=false`` to opt-in to deactivated rows;
    the default behaviour is to hide them.
    """

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("field_name", "is_active")
        super().__init__(*args, **kwargs)


class DateRangeFilter(django_filters.FilterSet):
    """Convenience for ``?created_after=...&created_before=...`` filters."""

    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")


__all__ = ["IsActiveFilter", "DateRangeFilter"]

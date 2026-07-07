"""Row-scoping for the INVIGILO RBAC model.

The matrix in ``docs/03-use-cases.md`` §3.1 maps a user's primary role
to the rows they may see. The mixin in this module applies that filter
to ``get_queryset``; the permission class on the view answers the
"may this user touch this kind of entity?" question.

Scope sources
------------
A subclass overrides one of:

* ``scope_field`` — a string. The filter is
  ``<scope_field> = request.user.<scope_value>``.

* ``scope_queryset`` — a callable ``(qs, request) -> qs``. The mixin
  calls it and returns the result.

If neither is set, the mixin is a no-op (use it on views where the
caller is allowed to see everything — typically SA-only views).
"""
from __future__ import annotations

from typing import Any, Callable

from django.db.models import Q, QuerySet
from rest_framework import mixins, viewsets


# Role -> (scope_field, scope_value_getter) — see 03-use-cases.md §3.1
# The default role is the highest-precedence role on the user. SA and EO
# see everything; IN sees only their own invigilator row; HOD sees their
# department; DEA sees their faculty.
def _invigilator_id(user: Any) -> str | None:
    inv = getattr(user, "invigilator", None)
    return getattr(inv, "id", None) if inv is not None else None


def _faculty_id(user: Any) -> str | None:
    dept = getattr(user, "primary_department", None)
    return getattr(dept.faculty, "id", None) if dept is not None else None


def _department_id(user: Any) -> str | None:
    dept = getattr(user, "primary_department", None)
    return getattr(dept, "id", None) if dept is not None else None


class ScopedQuerySetMixin:
    """Filter the view's queryset to the rows the user is allowed to see.

    Subclass and set ``scope_field`` (a tuple of model fields to constrain
    to the user's role scope) **or** ``scope_queryset``. Leave both unset
    to opt out of scoping (e.g. on SA-only views).
    """

    scope_field: str | tuple[str, ...] | None = None
    scope_queryset: Callable[[QuerySet, Any], QuerySet] | None = None
    # Optional: when True, the mixin will also expose ``get_queryset``-level
    # filters as instance methods (``filter_by_faculty``, ``filter_by_dept``)
    # for advanced views that need to compose the filter manually.
    expose_filter_helpers: bool = False

    def get_scope_for(self, user: Any) -> Q | None:
        """Return a Q object describing the rows the user may see, or None."""
        if user is None or not user.is_authenticated:
            return Q(pk__in=[])  # deny all

        # Superusers see everything.
        if user.is_superuser:
            return None

        role = user.primary_role_code
        if role in (None, "SYSTEM_ADMINISTRATOR", "EXAMINATION_OFFICER"):
            return None

        if role == "INVIGILATOR":
            inv_id = _invigilator_id(user)
            return Q(invigilator_id=inv_id) if inv_id else Q(pk__in=[])

        if role == "HEAD_OF_DEPARTMENT":
            dept_id = _department_id(user)
            return Q(department_id=dept_id) if dept_id else Q(pk__in=[])

        if role == "FACULTY_DEAN":
            faculty_id = _faculty_id(user)
            if not faculty_id:
                return Q(pk__in=[])
            return Q(department__faculty_id=faculty_id)

        return Q(pk__in=[])

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        qs = super().get_queryset()  # type: ignore[misc]
        scope = self.get_scope_for(self.request.user)
        if scope is not None:
            qs = qs.filter(scope)
        return qs


class ScopedViewSet(ScopedQuerySetMixin, viewsets.GenericViewSet):
    """A drop-in viewset base that applies row-scoping by role.

    Combine with DRF's mixins for the verbs you need::

        class StudentViewSet(ScopedViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
            ...
    """


__all__ = ["ScopedQuerySetMixin", "ScopedViewSet"]

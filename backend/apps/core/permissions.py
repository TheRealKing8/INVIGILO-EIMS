"""DRF permission classes for the INVIGILO RBAC model.

The contract — from ``docs/03-use-cases.md`` §3 — is that the role check
answers "may this user touch this kind of entity?" and the scoped
queryset (in :mod:`apps.core.scopes`) answers "which rows?".
"""
from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsSuperAdmin(IsAuthenticated):
    """Allow only users with the system-administrator flag set."""

    def has_permission(self, request: Any, view: Any) -> bool:
        user = request.user
        return bool(
            user and user.is_authenticated and (user.is_superuser or user.is_staff)
        )


class IsRole(BasePermission):
    """Allow only users whose effective role set includes one of ``roles``.

    Pass the role codes as a class attribute::

        class MyView(GenericViewSet):
            permission_classes = [IsAuthenticated, IsRole.with_roles("EXAMINATION_OFFICER")]
    """

    required_roles: tuple[str, ...] = ()

    @classmethod
    def with_roles(cls, *roles: str) -> type["IsRole"]:
        """Return a subclass bound to the given role codes."""
        return type(f"IsRole[{','.join(roles)}]", (cls,), {"required_roles": tuple(roles)})

    def has_permission(self, request: Any, view: Any) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if not self.required_roles:
            return True
        return any(user.has_role(r) for r in self.required_roles)


class HasPermission(BasePermission):
    """Allow only users who hold the named permission codename(s).

    Pass the codename(s) via the ``required_permissions`` attribute::

        class MyView(GenericViewSet):
            permission_classes = [IsAuthenticated, HasPermission.with_codes("people.invigilator.crud")]

    The view may also expose a ``required_permissions`` list; both are
    combined.
    """

    required_permissions: tuple[str, ...] = ()

    @classmethod
    def with_codes(cls, *codes: str) -> type["HasPermission"]:
        return type(
            f"HasPermission[{','.join(codes)}]",
            (cls,),
            {"required_permissions": tuple(codes)},
        )

    def has_permission(self, request: Any, view: Any) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        codes = self.required_permissions or tuple(getattr(view, "required_permissions", ()))
        if not codes:
            return True
        return all(user.has_permission(c) for c in codes)


__all__ = ["HasPermission", "IsRole", "IsSuperAdmin", "IsAuthenticated"]

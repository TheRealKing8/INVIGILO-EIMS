"""User-management service functions.

These wrap the ORM so views and management commands have a single entry
point. They raise :class:`apps.core.exceptions.DomainError` subclasses on
expected failure paths and let everything else bubble.
"""
from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)

from ..models import User, UserRole, Role


@transaction.atomic
def create_user(  # type: ignore[no-untyped-def]
    *,
    email: str,
    full_name: str,
    password: str | None = None,
    roles: list[str] | None = None,
    is_email_verified: bool = False,
    assigned_by: User | None = None,
    **extra_fields: Any,
) -> User:
    """Create a user and optionally assign roles.

    Raises ``ConflictError`` if the email is already taken. Raises
    ``ValidationFailedError`` if the password is not acceptable.
    """
    email_normalised = (email or "").strip().lower()
    if User.all_objects.filter(email__iexact=email_normalised).exists():
        raise ConflictError("A user with that email already exists.", extra={"email": email_normalised})

    if password is not None:
        try:
            validate_password(password)
        except Exception as exc:  # noqa: BLE001
            raise ValidationFailedError(str(exc)) from exc

    user = User.objects.create_user(
        email=email_normalised,
        full_name=full_name,
        password=password,
        is_email_verified=is_email_verified,
        **extra_fields,
    )

    for code in roles or []:
        try:
            role = Role.objects.get(code=code, is_active=True)
        except Role.DoesNotExist as exc:
            raise NotFoundError(f"Unknown role: {code}", extra={"role": code}) from exc
        UserRole.objects.create(user=user, role=role, assigned_by=assigned_by)

    return user


@transaction.atomic
def update_user(user: User, *, assigned_by: User | None = None, **fields: Any) -> User:
    """Apply a partial update to a user.

    Only known, safe fields are accepted; the rest are silently dropped
    to keep the API surface explicit.
    """
    safe = {
        "full_name",
        "phone",
        "avatar_url",
        "time_zone",
        "is_active",
        "is_email_verified",
    }
    for key, value in fields.items():
        if key in safe:
            setattr(user, key, value)
    user.save()
    return user


@transaction.atomic
def set_user_roles(user: User, role_codes: list[str], *, assigned_by: User | None = None) -> User:
    """Replace the user's role set with the given list.

    Unknown codes raise ``NotFoundError``. Existing assignments that are
    not in the new list are removed; the new ones are created with
    ``assigned_by`` recorded.
    """
    roles = list(Role.objects.filter(code__in=role_codes, is_active=True))
    found_codes = {r.code for r in roles}
    missing = set(role_codes) - found_codes
    if missing:
        raise NotFoundError(
            "Unknown role code(s).",
            extra={"missing": sorted(missing)},
        )

    UserRole.objects.filter(user=user).delete()
    for role in roles:
        UserRole.objects.create(user=user, role=role, assigned_by=assigned_by)
    return user


@transaction.atomic
def change_password(user: User, *, current: str, new: str) -> None:
    """Change a password given the current one.

    Raises ``PermissionDeniedError`` (from the service caller — this
    function raises ``ValidationFailedError``) if the current password
    is wrong. The service-level caller wraps it to set the right status.
    """
    if not user.check_password(current or ""):
        raise ValidationFailedError("Current password is incorrect.")
    try:
        validate_password(new, user=user)
    except Exception as exc:  # noqa: BLE001
        raise ValidationFailedError(str(exc)) from exc
    user.set_password(new)
    user.save(update_fields=("password", "updated_at"))


@transaction.atomic
def admin_reset_password(user: User, *, new: str) -> None:
    """Set a password on behalf of a user (e.g. after a manual unlock)."""
    try:
        validate_password(new, user=user)
    except Exception as exc:  # noqa: BLE001
        raise ValidationFailedError(str(exc)) from exc
    user.set_password(new)
    user.save(update_fields=("password", "updated_at"))


@transaction.atomic
def unlock_user(user: User) -> None:
    user.failed_login_count = 0
    user.locked_until = None
    user.save(update_fields=("failed_login_count", "locked_until", "updated_at"))


__all__ = [
    "admin_reset_password",
    "change_password",
    "create_user",
    "set_user_roles",
    "unlock_user",
    "update_user",
]

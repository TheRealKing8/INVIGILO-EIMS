"""Custom managers for the accounts app.

``UserManager`` is the standard manager with ``create_user`` and
``create_superuser``. ``SoftDeleteUserManager`` extends it with the
soft-delete filter so that ``User.objects`` excludes deactivated
accounts.
"""
from __future__ import annotations

from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.db import transaction

from apps.core.managers import SoftDeleteManager


class UserManager(BaseUserManager):
    """Manager for the email-as-username custom user."""

    use_in_migrations = True

    def _create_user(  # type: ignore[no-untyped-def]
        self,
        email: str,
        password: str | None,
        *,
        full_name: str,
        is_staff: bool = False,
        is_superuser: bool = False,
        is_email_verified: bool = False,
        **extra_fields: Any,
    ):
        if not email:
            raise ValueError("Email is required")
        if not full_name:
            raise ValueError("Full name is required")
        email = self.normalize_email(email)
        # `is_staff` and `is_superuser` come from PermissionsMixin on the
        # model; pass them through **extra_fields so we don't blow up the
        # constructor when they are repeated explicitly.
        user = self.model(
            email=email,
            full_name=full_name,
            is_email_verified=is_email_verified,
            is_staff=is_staff,
            is_superuser=is_superuser,
            **extra_fields,
        )
        if password is None:
            # Some flows (bulk import) defer setting a password until the
            # user accepts the verification link.
            user.set_unusable_password()
        else:
            user.set_password(password)
        user.save(using=self._db)
        return user

    @transaction.atomic
    def create_user(  # type: ignore[no-untyped-def]
        self,
        email: str,
        password: str | None = None,
        *,
        full_name: str,
        **extra_fields: Any,
    ):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(
            email=email,
            password=password,
            full_name=full_name,
            **extra_fields,
        )

    @transaction.atomic
    def create_superuser(  # type: ignore[no-untyped-def]
        self,
        email: str,
        password: str,
        *,
        full_name: str,
        **extra_fields: Any,
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(
            email=email,
            password=password,
            full_name=full_name,
            **extra_fields,
        )


class SoftDeleteUserManager(UserManager, SoftDeleteManager):
    """User manager that filters out soft-deleted (deactivated) accounts.

    The default ``User.objects`` uses this; the unfiltered manager is
    ``User.all_objects`` (``models.Manager()``).
    """

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return SoftDeleteManager.get_queryset(self)


__all__ = ["SoftDeleteUserManager", "UserManager"]


"""Account and identity models.

Schema mirrors ``docs/05-erd.md`` §2.1. Cross-app references are by
string (``settings.AUTH_USER_MODEL``) so the accounts app can be
referenced from anywhere without an import cycle.
"""
from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.managers import SoftDeleteManager
from apps.core.models import BaseModel, TimestampedModel, UUIDModel

from .managers import SoftDeleteUserManager, UserManager


# ----------------------------------------------------------------------------
# Roles & permissions
# ----------------------------------------------------------------------------
class Role(UUIDModel, TimestampedModel):
    """A named bundle of permissions.

    Role codes are stable identifiers (``EXAMINATION_OFFICER`` etc.)
    used by the RBAC matrix. The display name is what the UI shows.
    """

    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} — {self.name}"


class Permission(UUIDModel, TimestampedModel):
    """An atomic capability, identified by a dot-path codename.

    Permission codenames are the contract that views, services, and the
    frontend share. Adding a new one requires a database migration that
    seeds the row, plus an entry in the role/permission matrix.
    """

    codename = models.CharField(max_length=128, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("codename",)

    def __str__(self) -> str:  # pragma: no cover
        return self.codename


class RolePermission(UUIDModel, TimestampedModel):
    """M2M between :class:`Role` and :class:`Permission`."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="permission_roles"
    )

    class Meta:
        unique_together = (("role", "permission"),)
        indexes = [models.Index(fields=("role", "permission"))]


# ----------------------------------------------------------------------------
# User
# ----------------------------------------------------------------------------
class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """The single user table.

    Identity is email + password. ``is_staff`` controls Django admin
    access; ``is_superuser`` is the super-admin flag. ``is_email_verified``
    blocks login until the user accepts the verification link.
    """

    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True, default="")
    avatar_url = models.URLField(blank=True, default="")
    time_zone = models.CharField(max_length=64, default="UTC")

    is_email_verified = models.BooleanField(default=False, db_index=True)
    is_staff = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates whether the user can log into the Django admin.",
    )
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ("full_name",)

    # Use the soft-delete-aware default manager so that ``User.objects``
    # excludes deactivated accounts. The hard manager is ``User.all_objects``.
    # ``PermissionsMixin`` would normally install its own manager, but we
    # override it here.
    objects = SoftDeleteUserManager()
    all_objects = UserManager()

    class Meta:
        ordering = ("email",)
        base_manager_name = "all_objects"
        indexes = [
            models.Index(fields=("is_active", "is_email_verified")),
        ]

    # --- String ------------------------------------------------------------
    def __str__(self) -> str:  # pragma: no cover
        return f"{self.full_name} <{self.email}>"

    # --- Role helpers ------------------------------------------------------
    def roles(self) -> models.QuerySet[Role]:
        return Role.objects.filter(role_users__user=self)

    def permissions(self) -> models.QuerySet[Permission]:
        return Permission.objects.filter(
            permission_roles__role__role_users__user=self
        ).distinct()

    def has_role(self, code: str) -> bool:
        return self.roles().filter(code=code, is_active=True).exists()

    @property
    def primary_role_code(self) -> str | None:
        """Return the highest-precedence role code on the user.

        The order matches ``docs/03-use-cases.md`` §3 — SA wins over
        everyone, then EO, then the department-level roles
        (FACULTY_DEAN, HEAD_OF_DEPARTMENT), then INVIGILATOR, then the
        low-trust operational roles (SECURITY_OFFICER, STUDENT, GUEST).
        A user with multiple roles (e.g. a HOD who is also an
        invigilator) gets the highest.
        """
        order = (
            "SYSTEM_ADMINISTRATOR",
            "EXAMINATION_OFFICER",
            "FACULTY_DEAN",
            "HEAD_OF_DEPARTMENT",
            "INVIGILATOR",
            "SECURITY_OFFICER",
            "STUDENT",
            "GUEST",
        )
        codes = set(self.roles().filter(is_active=True).values_list("code", flat=True))
        for code in order:
            if code in codes:
                return code
        return None

    def has_permission(self, codename: str) -> bool:
        if self.is_superuser:
            return True
        return self.permissions().filter(codename=codename).exists()

    # --- Role/permission assignment ----------------------------------------
    def assign_role(self, role: Role, *, assigned_by: "User | None" = None) -> None:
        UserRole.objects.get_or_create(
            user=self,
            role=role,
            defaults={"assigned_by": assigned_by},
        )

    def remove_role(self, role: Role) -> None:
        UserRole.objects.filter(user=self, role=role).delete()

    # --- Lockout -----------------------------------------------------------
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_login(self) -> None:
        from django.conf import settings as dj_settings

        self.failed_login_count += 1
        if self.failed_login_count >= dj_settings.LOCKOUT_THRESHOLD:
            self.locked_until = timezone.now() + timezone.timedelta(
                minutes=dj_settings.LOCKOUT_DURATION_MINUTES
            )
        self.save(update_fields=("failed_login_count", "locked_until", "updated_at"))

    def register_successful_login(self) -> None:
        self.failed_login_count = 0
        self.locked_until = None
        self.last_login_at = timezone.now()
        self.save(
            update_fields=("failed_login_count", "locked_until", "last_login_at", "updated_at")
        )


class UserRole(UUIDModel, TimestampedModel):
    """M2M between :class:`User` and :class:`Role`."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_roles"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_users")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        unique_together = (("user", "role"),)
        indexes = [models.Index(fields=("user", "role"))]


# ----------------------------------------------------------------------------
# Tokens
# ----------------------------------------------------------------------------
class RefreshToken(UUIDModel, TimestampedModel):
    """A persistent refresh token, hashed at rest.

    The raw token is returned to the client only on creation; subsequent
    requests send it back, we hash it, and look it up. ``replaced_by``
    tracks the rotation chain so we can revoke the entire chain on
    password change.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="refresh_tokens"
    )
    token_hash = models.CharField(max_length=128, unique=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    replaced_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predecessor",
    )
    user_agent = models.CharField(max_length=512, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()

    def revoke(self) -> None:
        self.revoked_at = timezone.now()
        self.save(update_fields=("revoked_at", "updated_at"))


class EmailVerification(UUIDModel, TimestampedModel):
    """A signed token used to verify a user's email address."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_verifications"
    )
    token_hash = models.CharField(max_length=128, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class PasswordReset(UUIDModel, TimestampedModel):
    """A signed token used to authorise a password reset."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_resets"
    )
    token_hash = models.CharField(max_length=128, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class LoginOTP(UUIDModel, TimestampedModel):
    """A one-time code for the second step of admin login.

    The :class:`otp_token` is an opaque, random, *public* identifier —
    it's the value returned to the client and used to look the row up
    on the verify step. The :class:`code_hash` is the argon2id hash of
    the 6-digit code itself, so a database leak doesn't expose the
    codes. After five failed attempts or successful consumption, the
    row is marked ``consumed_at`` so the same ``otp_token`` can never
    be reused.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="login_otps"
    )
    otp_token = models.CharField(max_length=64, unique=True, db_index=True)
    code_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    MAX_ATTEMPTS = 5

    def is_usable(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()


__all__ = [
    "EmailVerification",
    "LoginOTP",
    "PasswordReset",
    "Permission",
    "RefreshToken",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
]

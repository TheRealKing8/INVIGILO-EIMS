"""Authentication services.

The login, refresh, logout, password-reset, and email-verification flows
live here. Views are thin: they call into these functions and shape the
HTTP response.

The refresh-token model is hand-rolled (see :class:`apps.accounts.models.RefreshToken`)
because the SimpleJWT library doesn't expose a clean way to revoke a
chain on password change. We still use SimpleJWT to **sign** the access
tokens — only the refresh-token storage is custom.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Any

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken as _SimpleJWTRefresh

from apps.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)

from ..models import (
    EmailVerification,
    PasswordReset,
    RefreshToken,
    User,
)


# ----------------------------------------------------------------------------
# Hashing
# ----------------------------------------------------------------------------
def _hash_token(raw: str) -> str:
    """Hash a raw token (client-side) for at-rest storage."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------
# Login
# ----------------------------------------------------------------------------
def authenticate(email: str, password: str) -> User:
    """Verify email + password, taking lockout into account.

    Raises ``AuthenticationError`` for any failure (wrong credentials,
    unverified email, locked account). On success, resets the failed
    counter and returns the user.
    """
    user = User.all_objects.filter(email__iexact=(email or "").strip().lower()).first()
    if user is None:
        # Constant-time delay: avoid a timing oracle between "no such user"
        # and "wrong password".
        User.set_password(User(_dummy_password := User()), "x")
        raise AuthenticationError("Invalid credentials.")

    if user.is_locked():
        raise PermissionDeniedError(
            "Account is temporarily locked. Try again later.",
            extra={"locked_until": user.locked_until.isoformat() if user.locked_until else None},
        )

    if not user.is_email_verified:
        raise PermissionDeniedError(
            "Email address has not been verified.",
            extra={"code": "email_unverified"},
        )

    if not user.check_password(password or ""):
        user.register_failed_login()
        raise AuthenticationError("Invalid credentials.")

    if not user.is_active:
        raise PermissionDeniedError("Account is disabled.")

    user.register_successful_login()
    return user


def issue_token_pair(user: User, *, request: Any = None) -> dict[str, Any]:
    """Issue an access + refresh pair for the given user.

    The refresh token is generated with ``secrets`` (not by SimpleJWT) so
    we can hash and persist it. The access token is signed with
    SimpleJWT; it carries the user id, primary role, and the full set
    of permission codenames granted to the user (the union across all
    active roles, not just the primary one). The frontend uses
    ``permissions`` for client-side gating; the server is still the
    source of truth and re-checks ``HasPermission`` on every request.
    """
    # Build the permission set once and reuse for the JWT claim and the
    # response payload. ``user.permissions()`` is a queryset; we
    # materialise it to a list to avoid round-tripping for the two
    # consumers below.
    permission_codes: list[str] = list(
        user.permissions().values_list("codename", flat=True)
    )

    access = AccessToken()
    access["user_id"] = str(user.id)
    access["email"] = user.email
    access["role"] = user.primary_role_code
    access["permissions"] = permission_codes
    access["iss"] = settings.SIMPLE_JWT["ISSUER"]
    access["aud"] = settings.SIMPLE_JWT["AUDIENCE"]

    raw_refresh = secrets.token_urlsafe(48)
    refresh_hash = _hash_token(raw_refresh)
    expires_at = timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]

    user_agent = ""
    ip_address = None
    if request is not None:
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip_address = (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) or None

    RefreshToken.objects.create(
        user=user,
        token_hash=refresh_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    return {
        "access": str(access),
        "refresh": raw_refresh,
        "access_lifetime_seconds": int(
            settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()
        ),
        "refresh_lifetime_seconds": int(
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()
        ),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.primary_role_code,
            "permissions": permission_codes,
            "is_email_verified": user.is_email_verified,
        },
    }


# ----------------------------------------------------------------------------
# Refresh
# ----------------------------------------------------------------------------
def rotate_refresh(raw: str) -> dict[str, Any]:
    """Exchange a refresh token for a new pair.

    The old row is marked revoked; a new row is created. The chain is
    monotonic, so detecting token-reuse is straightforward: if a revoked
    token is presented again, we revoke the entire chain for that user
    (NIST SP 800-63B).
    """
    if not raw:
        raise AuthenticationError("Missing refresh token.")
    token_hash = _hash_token(raw)
    try:
        row = RefreshToken.objects.select_related("user").get(token_hash=token_hash)
    except RefreshToken.DoesNotExist as exc:
        raise AuthenticationError("Invalid refresh token.") from exc

    if not row.is_active():
        # Possible reuse — revoke everything for this user.
        RefreshToken.objects.filter(user=row.user, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        raise AuthenticationError("Refresh token has been revoked or expired.")

    row.revoke()
    return issue_token_pair(row.user)


# ----------------------------------------------------------------------------
# Logout
# ----------------------------------------------------------------------------
def revoke_refresh(raw: str) -> None:
    """Revoke a refresh token (logout). Idempotent."""
    if not raw:
        return
    token_hash = _hash_token(raw)
    RefreshToken.objects.filter(token_hash=token_hash, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )


# ----------------------------------------------------------------------------
# Email verification
# ----------------------------------------------------------------------------
def issue_email_verification(user: User) -> str:
    """Create a verification token and return the raw value.

    The raw token is what we put in the email link. The hashed value is
    what we persist.
    """
    raw = secrets.token_urlsafe(32)
    EmailVerification.objects.create(
        user=user,
        token_hash=_hash_token(raw),
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )
    return raw


def confirm_email_verification(raw: str) -> User:
    """Consume a verification token; return the user (now verified)."""
    if not raw:
        raise ValidationFailedError("Missing verification token.")
    try:
        row = EmailVerification.objects.select_related("user").get(token_hash=_hash_token(raw))
    except EmailVerification.DoesNotExist as exc:
        raise NotFoundError("Verification token not found.") from exc
    if not row.is_usable():
        raise ValidationFailedError("Verification token has expired or been used.")
    row.used_at = timezone.now()
    row.save(update_fields=("used_at", "updated_at"))
    user = row.user
    user.is_email_verified = True
    user.save(update_fields=("is_email_verified", "updated_at"))
    return user


# ----------------------------------------------------------------------------
# Password reset
# ----------------------------------------------------------------------------
def issue_password_reset(email: str) -> str | None:
    """Create a reset token. Returns the raw token, or ``None`` if the user
    does not exist. The endpoint must return the same response either way
    to avoid email enumeration.
    """
    user = User.all_objects.filter(email__iexact=(email or "").strip().lower()).first()
    if user is None:
        return None
    raw = secrets.token_urlsafe(32)
    PasswordReset.objects.create(
        user=user,
        token_hash=_hash_token(raw),
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )
    return raw


def confirm_password_reset(raw: str, new_password: str) -> None:
    """Consume a reset token; set the new password; revoke all refresh
    tokens for the user.
    """
    if not raw:
        raise ValidationFailedError("Missing reset token.")
    try:
        row = PasswordReset.objects.select_related("user").get(token_hash=_hash_token(raw))
    except PasswordReset.DoesNotExist as exc:
        raise NotFoundError("Reset token not found.") from exc
    if not row.is_usable():
        raise ValidationFailedError("Reset token has expired or been used.")
    try:
        validate_password(new_password, user=row.user)
    except Exception as exc:  # noqa: BLE001
        raise ValidationFailedError(str(exc)) from exc
    row.user.set_password(new_password)
    row.user.save(update_fields=("password", "updated_at"))
    row.used_at = timezone.now()
    row.save(update_fields=("used_at", "updated_at"))
    RefreshToken.objects.filter(user=row.user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )


__all__ = [
    "authenticate",
    "confirm_email_verification",
    "confirm_password_reset",
    "issue_email_verification",
    "issue_password_reset",
    "issue_token_pair",
    "revoke_refresh",
    "rotate_refresh",
]

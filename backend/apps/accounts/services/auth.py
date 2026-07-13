"""Authentication services.

The login, refresh, logout, password-reset, and email-verification flows
live here. Views are thin: they call into these functions and shape the
HTTP response.

The refresh-token model is hand-rolled (see :class:`apps.accounts.models.RefreshToken`)
because the SimpleJWT library doesn't expose a clean way to revoke a
chain on password change. We still use SimpleJWT to **sign** the access
tokens — only the refresh-token storage is custom.

The refresh token is delivered to the client as an httpOnly cookie
(``invigilo_rt``) by default, not as a JSON body field. JavaScript
running in the browser cannot read it; only the API can, when the
browser attaches it to subsequent requests. The raw token is still
returned in the response body for the cases that need it
(non-browser clients, tests) — the visibility is controlled by
``settings.JWT_INCLUDE_REFRESH_IN_BODY``.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.http import HttpResponse
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.exceptions import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)

from ..models import (
    EmailVerification,
    LoginOTP,
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
# Cookie helpers
# ----------------------------------------------------------------------------
def _cookie_max_age() -> int:
    """Cookie lifetime in seconds, matching the refresh-token lifetime."""
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_refresh_cookie(response: HttpResponse, raw_refresh: str) -> None:
    """Attach the refresh token as an httpOnly cookie on ``response``.

    The cookie is the primary channel; JavaScript cannot read it. The
    ``Secure`` flag follows ``settings.JWT_REFRESH_COOKIE_SECURE`` —
    on in production (DEBUG=False), off in development so the local
    http://127.0.0.1 flow still works.
    """
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        raw_refresh,
        max_age=_cookie_max_age(),
        expires=_cookie_max_age(),
        path=settings.JWT_REFRESH_COOKIE_PATH,
        domain=settings.JWT_REFRESH_COOKIE_DOMAIN or None,
        secure=settings.JWT_REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response: HttpResponse) -> None:
    """Tell the browser to drop the refresh cookie. Idempotent."""
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_REFRESH_COOKIE_PATH,
        domain=settings.JWT_REFRESH_COOKIE_DOMAIN or None,
    )


def read_refresh_from_request(request: Any) -> Optional[str]:
    """Return the raw refresh token from the request, preferring the
    cookie (the production path) and falling back to the body
    (the legacy / non-browser path and the test path)."""
    cookie = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME) if hasattr(request, "COOKIES") else None
    if cookie:
        return cookie
    body_value: Optional[str] = None
    if hasattr(request, "data") and isinstance(request.data, dict):
        raw = request.data.get("refresh")
        if isinstance(raw, str):
            body_value = raw
    return cookie or body_value


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


def issue_token_pair(
    user: User,
    *,
    request: Any = None,
    response: Any = None,
) -> dict[str, Any]:
    """Issue an access + refresh pair for the given user.

    The refresh token is generated with ``secrets`` (not by SimpleJWT) so
    we can hash and persist it. The access token is signed with
    SimpleJWT; it carries the user id, primary role, and the full set
    of permission codenames granted to the user (the union across all
    active roles, not just the primary one). The frontend uses
    ``permissions`` for client-side gating; the server is still the
    source of truth and re-checks ``HasPermission`` on every request.

    The refresh token is delivered to the client via an httpOnly
    cookie (see :func:`set_refresh_cookie`). It's still included in
    the response body when ``settings.JWT_INCLUDE_REFRESH_IN_BODY``
    is true — for non-browser clients and tests.
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

    # Always set the cookie when we have a response. Login/register
    # pass the DRF Response in; rotation passes the new Response too.
    if response is not None:
        set_refresh_cookie(response, raw_refresh)

    body: dict[str, Any] = {
        "access": str(access),
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
    if settings.JWT_INCLUDE_REFRESH_IN_BODY:
        body["refresh"] = raw_refresh
    return body


# ----------------------------------------------------------------------------
# Refresh
# ----------------------------------------------------------------------------
def rotate_refresh(
    raw: str,
    *,
    request: Any = None,
    response: Any = None,
) -> dict[str, Any]:
    """Exchange a refresh token for a new pair.

    The old row is marked revoked; a new row is created. The chain is
    monotonic, so detecting token-reuse is straightforward: if a revoked
    token is presented again, we revoke the entire chain for that user
    (NIST SP 800-63B).

    If ``response`` is provided, the new refresh is delivered as an
    httpOnly cookie and the old cookie is overwritten.
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
    return issue_token_pair(row.user, request=request, response=response)


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


# ----------------------------------------------------------------------------
# Login OTP (admin second factor)
# ----------------------------------------------------------------------------
# Argon2id hasher for the 6-digit code. Tuned for interactive
# verification — we don't need the long-running params we'd use for
# password storage, because the input is exactly 6 decimal digits
# (~30 bits of entropy) and the verification is on the request path.
_OTP_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=2 ** 16,  # 64 MiB
    parallelism=2,
)


def _generate_otp_code() -> str:
    """Return a fresh 6-digit code, zero-padded."""
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_login_otp(user: User) -> tuple[str, str]:
    """Create a LoginOTP row for ``user`` and return ``(otp_token, code)``.

    The ``otp_token`` is the opaque, public identifier (returned to the
    client). The ``code`` is the 6-digit secret the user types in. The
    DB stores the argon2id hash of the code, never the code itself.

    Any unconsumed, unexpired OTPs for the same user are revoked first
    — so each login attempt has exactly one active code at a time and
    the most recent email is the one that matters.
    """
    # Revoke any prior unconsumed codes for this user so a new
    # request replaces an old one cleanly.
    LoginOTP.objects.filter(user=user, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )
    otp_token = secrets.token_urlsafe(32)
    code = _generate_otp_code()
    LoginOTP.objects.create(
        user=user,
        otp_token=otp_token,
        code_hash=_OTP_HASHER.hash(code),
        expires_at=timezone.now() + timezone.timedelta(minutes=10),
    )
    return otp_token, code


def consume_login_otp(otp_token: str, code: str) -> Optional[User]:
    """Validate ``(otp_token, code)`` and return the user on success.

    Returns ``None`` for any failure mode — wrong code, expired token,
    exhausted attempts, unknown token. We deliberately collapse every
    failure into a single ``None`` return so an attacker can't tell
    *why* it failed (timing, brute force, replay detection).

    On a successful verify, the row is marked ``consumed_at`` and
    the user is returned. On any failure, ``attempts`` is incremented
    and the row is revoked once ``MAX_ATTEMPTS`` is reached so the
    same ``otp_token`` can't be retried indefinitely.
    """
    if not otp_token or not code:
        return None
    try:
        row = LoginOTP.objects.select_related("user").get(otp_token=otp_token)
    except LoginOTP.DoesNotExist:
        return None
    if not row.is_usable():
        return None
    row.attempts += 1
    try:
        _OTP_HASHER.verify(row.code_hash, code)
    except VerifyMismatchError:
        # Persist the incremented attempt count; revoke on threshold.
        update_fields = ("attempts", "updated_at")
        if row.attempts >= LoginOTP.MAX_ATTEMPTS:
            row.consumed_at = timezone.now()
            update_fields = ("attempts", "consumed_at", "updated_at")
        row.save(update_fields=update_fields)
        return None
    row.consumed_at = timezone.now()
    row.save(update_fields=("consumed_at", "updated_at"))
    return row.user


def requires_login_otp(user: User) -> bool:
    """Return True if ``user`` must complete the OTP second step.

    Currently this is any user that holds the SYSTEM_ADMINISTRATOR
    role. Kept as a single function so the policy can be widened
    later (e.g. EXAMINATION_OFFICER) without touching the view.
    """
    if user.is_superuser:
        return True
    return user.has_role("SYSTEM_ADMINISTRATOR")


__all__ = [
    "authenticate",
    "clear_refresh_cookie",
    "confirm_email_verification",
    "confirm_password_reset",
    "consume_login_otp",
    "issue_email_verification",
    "issue_login_otp",
    "issue_password_reset",
    "issue_token_pair",
    "read_refresh_from_request",
    "requires_login_otp",
    "revoke_refresh",
    "rotate_refresh",
    "set_refresh_cookie",
]

"""QR token issuing + verification (Phase 19).

A QrToken is a short-lived, signed, revocable string that encodes
"this QR is the right for subject X until expires_at". The wire
format is::

    <subject>:<expires_at_epoch>:<hmac_hex>

where ``subject`` is::

    * ``r<registration_id>`` for student tokens (the scanner needs
      the registration_id to look up the StudentRegistration row)
    * ``u<user_id>`` for staff tokens (the scanner checks the user
      into the room — the staff member's role decides which kind
      of CheckIn is created)

and ``hmac_hex`` is HMAC-SHA256(secret, "<subject>:<expires_at_epoch>")
using the project's ``JWT_SIGNING_KEY``. Reusing the JWT signing key
is deliberate: the secret is already high-trust, already 32+ bytes,
and rotation has the same blast radius either way. Splitting the
keys would only double the rotation burden with no security benefit.

The DB row stores a SHA-256 of the full token (``token_hash``), not
the raw token. A leaked DB row therefore reveals which tokens have
been issued, but never lets an attacker reconstruct the bytes that
sit in the printed QR.

Why HMAC + DB and not just HMAC?

  * HMAC alone: the scanner can verify *any* token signed by us.
    Once a QR is printed, it remains valid until the TTL expires.
  * HMAC + DB: the operator can revoke a single token in real time
    (e.g. a student's lost card). The DB lookup happens on every
    scan, so revocation is instant.

Together: HMAC stops a screenshot-or-URL-attacker from forging
tokens, the TTL stops a screenshot being useful for more than 60s,
and the DB check stops an ex-employee from using a token that was
valid five minutes ago.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .student_registration import QrToken, StudentRegistration


# Default TTLs. 60s for students (printed cards, screenshot attacks),
# 5min for staff (phone screens, repeated re-scan of the same person).
STUDENT_TOKEN_TTL_SECONDS = 60
STAFF_TOKEN_TTL_SECONDS = 5 * 60


class QrTokenError(Exception):
    """Base class for QR token errors."""


class QrTokenInvalid(QrTokenError):
    """The token is malformed, signed by a different key, or has expired."""


class QrTokenRevoked(QrTokenError):
    """The token was valid but has been explicitly revoked."""


class QrTokenUnknown(QrTokenError):
    """No QrToken row matches the supplied hash."""


@dataclass
class VerifiedStaffToken:
    """What the scanner needs to do its work for a staff token."""
    user_id: str
    token_row: QrToken


@dataclass
class VerifiedStudentToken:
    """What the scanner needs to do its work for a student token."""
    registration: StudentRegistration
    session_id: str
    token_row: QrToken


def _signing_key() -> bytes:
    """Read the HMAC key from settings; never log this.

    Falls back to ``SECRET_KEY`` if neither ``JWT_SIGNING_KEY`` nor
    ``SIMPLE_JWT['SIGNING_KEY']`` is set (parity with DRF SimpleJWT,
    which does the same fallback in the JWT serializer).
    """
    key = (
        getattr(settings, "JWT_SIGNING_KEY", None)
        or settings.SIMPLE_JWT.get("SIGNING_KEY")
        or settings.SECRET_KEY
    )
    if not key:
        raise RuntimeError("QR token signing key is not configured")
    return key.encode("utf-8") if isinstance(key, str) else key


def _hmac_hex(subject: str, expires_at_epoch: int, nonce: str) -> str:
    payload = f"{subject}:{expires_at_epoch}:{nonce}".encode("utf-8")
    return hmac.new(_signing_key(), payload, hashlib.sha256).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now_epoch() -> int:
    return int(timezone.now().timestamp())


# ---------------------------------------------------------------------------
# Issue
# ---------------------------------------------------------------------------
def issue_student_qr_token(
    registration: StudentRegistration,
    *,
    ttl_seconds: int = STUDENT_TOKEN_TTL_SECONDS,
) -> tuple[str, QrToken]:
    """Mint a fresh signed token for a student registration.

    Returns ``(raw_token, row)`` where ``raw_token`` is the
    base64url-shaped string to encode in the QR, and ``row`` is the
    persisted :class:`QrToken` (so the caller can mark it revoked
    later if needed).

    Re-issuing on every page load is the expected pattern — the
    student card re-prints every 60s and the printed PNG is the
    short-lived artifact. The DB is the audit trail; the HMAC is
    the auth.
    """
    now = timezone.now()
    expires_at = now + timedelta(seconds=ttl_seconds)
    expires_epoch = int(expires_at.timestamp())
    nonce = secrets.token_hex(8)  # 16 hex chars; distinct per issue
    subject = f"r{registration.id}"
    sig = _hmac_hex(subject, expires_epoch, nonce)
    raw = f"{subject}:{expires_epoch}:{nonce}:{sig}"
    row = QrToken.objects.create(
        token_hash=_hash_token(raw),
        kind="student",
        scope="session",
        session=registration.session,
        registration=registration,
        user=None,
        expires_at=expires_at,
    )
    return raw, row


def issue_staff_qr_token(
    user,
    *,
    ttl_seconds: int = STAFF_TOKEN_TTL_SECONDS,
) -> tuple[str, QrToken]:
    """Mint a signed token for an invigilator / EO / admin staff member.

    A staff token is not bound to a specific session — the scanner
    uses the staff member's role + allocation table to decide which
    kind of CheckIn to create. The TTL is longer (5min) so the
    invigilator can re-scan themselves in after a brief WiFi blip.
    """
    now = timezone.now()
    expires_at = now + timedelta(seconds=ttl_seconds)
    expires_epoch = int(expires_at.timestamp())
    nonce = secrets.token_hex(8)
    subject = f"u{user.id}"
    sig = _hmac_hex(subject, expires_epoch, nonce)
    raw = f"{subject}:{expires_epoch}:{nonce}:{sig}"
    row = QrToken.objects.create(
        token_hash=_hash_token(raw),
        kind="staff",
        scope="self",
        session=None,
        registration=None,
        user=user,
        expires_at=expires_at,
    )
    return raw, row


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
def _split_token(raw: str) -> tuple[str, int, str, str]:
    """Parse the wire format. Raises :class:`QrTokenInvalid` on bad shape.

    The wire format is ``<subject>:<expires_at_epoch>:<nonce>:<sig>``
    — the nonce is a per-issue random salt so two tokens minted in
    the same second for the same subject don't collide on the
    unique ``token_hash`` index.
    """
    if not raw or not isinstance(raw, str):
        raise QrTokenInvalid("empty token")
    parts = raw.split(":")
    if len(parts) != 4:
        raise QrTokenInvalid("malformed token (expected subject:exp:nonce:sig)")
    subject, exp_str, nonce, sig = parts
    try:
        expires_at_epoch = int(exp_str)
    except ValueError as exc:
        raise QrTokenInvalid("malformed expiry") from exc
    if not (sig and subject and nonce):
        raise QrTokenInvalid("empty subject, nonce, or signature")
    return subject, expires_at_epoch, nonce, sig


def _verify_signature(
    subject: str, expires_at_epoch: int, nonce: str, sig: str
) -> None:
    expected = _hmac_hex(subject, expires_at_epoch, nonce)
    if not hmac.compare_digest(expected, sig):
        raise QrTokenInvalid("bad signature")


def verify_qr_token(raw: str) -> QrToken:
    """Verify a raw token and return the matching :class:`QrToken` row.

    The order of checks is deliberate and matters for the threat model:

      1. **Parse**: malformed tokens are rejected without a DB hit.
      2. **Signature**: a token signed with the wrong key is
         rejected without a DB hit. Stops URL tampering.
      3. **Expiry**: an expired token is rejected without a DB hit.
         Stops screenshot reuse past the TTL.
      4. **DB lookup** (by hash): the row gives us the revocation
         status. The hash means a stolen DB row doesn't leak the
         raw token, but does let us look up the row from the raw
         token that was actually printed.
      5. **Revocation**: an explicitly revoked token is rejected.

    Returns the live :class:`QrToken` row. The caller decides what
    to do with it (resolve to a registration, mark consumed, etc.).
    """
    subject, expires_epoch, nonce, sig = _split_token(raw)
    _verify_signature(subject, expires_epoch, nonce, sig)
    if expires_epoch < _now_epoch():
        raise QrTokenInvalid("token expired")
    try:
        row = QrToken.objects.select_related(
            "registration", "registration__session", "registration__student", "user"
        ).get(token_hash=_hash_token(raw))
    except QrToken.DoesNotExist as exc:
        raise QrTokenUnknown("token not found") from exc
    if row.is_revoked:
        raise QrTokenRevoked("token has been revoked")
    return row


def resolve_for_scan(row: QrToken):
    """Return the right ``Verified*Token`` for a verified row.

    Used by the scan endpoint: callers don't need to know whether
    the row is student- or staff-shaped — they get a tagged result
    they can dispatch on.
    """
    if row.kind == "student":
        if not row.registration_id:
            raise QrTokenInvalid("student token missing registration")
        return VerifiedStudentToken(
            registration=row.registration,
            session_id=str(row.session_id),
            token_row=row,
        )
    if row.kind == "staff":
        if not row.user_id:
            raise QrTokenInvalid("staff token missing user")
        return VerifiedStaffToken(user_id=str(row.user_id), token_row=row)
    raise QrTokenInvalid(f"unknown token kind: {row.kind!r}")


__all__ = [
    "QrTokenError",
    "QrTokenInvalid",
    "QrTokenRevoked",
    "QrTokenUnknown",
    "STUDENT_TOKEN_TTL_SECONDS",
    "STAFF_TOKEN_TTL_SECONDS",
    "VerifiedStaffToken",
    "VerifiedStudentToken",
    "issue_student_qr_token",
    "issue_staff_qr_token",
    "verify_qr_token",
    "resolve_for_scan",
]

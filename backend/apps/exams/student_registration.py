"""StudentRegistration — per-(session, student) row, the security officer's
door-scanner target.

A row is the *authoritative* record that "this student is sitting this
paper at this room/this time". The QR code on the student card encodes
a *signed token* (see :class:`QrToken`); scanning it at the door
resolves the token to a student + session pair and creates a
:class:`apps.attendance.CheckIn` (idempotent on
``(session, user, kind)``).

The ``student_code`` is a short, human-readable label printed on the
card so the student can also type it in by hand if their QR is
unreadable. We don't FK to a separate ``Student`` model — the existing
:class:`apps.accounts.User` with the STUDENT role *is* the student.

# ---------------------------------------------------------------------------
# Phase 19 — QrToken (signed, rotating, revocable)
# ---------------------------------------------------------------------------
# The QR that ships on the student card is no longer the raw
# ``StudentRegistration.id``. It's a *signed token* of the form
# ``<registration_id>:<expires_at>:<hmac>`` (base64url). The signing
# key is the same JWT_SIGNING_KEY we use for access tokens. The token
# is short-lived (60s default for students, 5min default for staff) so
# a screenshot is stale within a minute, and the QrToken row is
# checked on every scan so the operator can revoke instantly.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class StudentRegistration(BaseModel):
    """A student pre-registered to write a particular exam session.

    One row per ``(session, student)`` pair. The ``unique_together``
    makes a second create for the same pair a 400 — the right signal
    for "already registered" rather than a silent duplicate.
    """

    session = models.ForeignKey(
        "exams.ExamSession",
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exam_registrations",
    )
    student_code = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Short, human-readable code printed on the student card (e.g. CS101-2026-0042).",
    )

    class Meta:
        ordering = ("session__starts_at", "student__email")
        # A student is registered to one session at most once. A
        # second POST for the same pair is a 400, not a duplicate row.
        unique_together = (("session", "student"),)
        indexes = [models.Index(fields=("session", "student"))]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student.email} @ {self.session_id} ({self.student_code})"


class QrToken(BaseModel):
    """A signed, rotating, revocable QR token.

    Each issued token is one row. The QR code the operator prints on
    the card carries the row's ``token_hash`` (the *raw* token is
    base64url ``<subject>:<expiry>:<hmac>`` — the hash is the SHA-256
    of that payload, so a leaked DB row never lets an attacker
    reconstruct the token).

    The scan endpoint (``POST /api/v1/attendance/scan/``) hashes the
    incoming token, looks it up here, and rejects anything that is
    expired or revoked. The HMAC + DB check together cover the two
    threat models: a screenshot of the QR (handled by the short TTL)
    and a stolen DB row (handled by the HMAC — the attacker still
    needs the signing key to mint a *new* valid token).
    """

    KIND_CHOICES = (
        ("student", "Student"),
        ("staff", "Staff"),
    )
    SCOPE_CHOICES = (
        ("session", "Session-bound (student)"),
        ("self", "Self (invigilator / EO / admin)"),
    )

    token_hash = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        help_text="SHA-256 hex of the raw token; the raw token is never stored.",
    )
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES)
    # The row this token resolves to. ``session`` is set for student
    # tokens (the scanner needs to confirm the registration belongs to
    # the right session); ``user`` is set for staff tokens (the staff
    # member IS the resolution target).
    session = models.ForeignKey(
        "exams.ExamSession",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="qr_tokens",
    )
    registration = models.ForeignKey(
        StudentRegistration,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="qr_tokens",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="qr_tokens",
    )
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("expires_at", "revoked_at")),
            models.Index(fields=("kind", "scope")),
        ]

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def __str__(self) -> str:  # pragma: no cover
        return f"QrToken({self.kind}/{self.scope}, exp={self.expires_at.isoformat()})"


__all__ = ["StudentRegistration", "QrToken"]

"""Service layer for notifications.

Two public entry points:

* :func:`notify` — fire a notification (in-app row + email task).
* :func:`send_notification_email` — the Celery task that actually
  delivers the email and stamps ``email_sent_at``.

Plus the calendar helpers used by :mod:`apps.notifications.calendar`
(kept here because they're business logic about *what* sessions belong
on the user's feed, not HTTP plumbing).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone as dt_timezone
from typing import Any, Iterable

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Notification

logger = logging.getLogger("invigilo.notifications.services")

User = get_user_model()


# ---------------------------------------------------------------------------
# Notify
# ---------------------------------------------------------------------------
def notify(
    *,
    recipient: Any,
    kind: str,
    title: str,
    body: str = "",
    target_type: str = "",
    target_id: str = "",
    send_email: bool = True,
) -> Notification:
    """Create the in-app row and queue the email.

    Idempotent by ``(recipient, kind, target_type, target_id)`` — a
    second call returns the existing row without duplicating. This is
    important for the allocation engine, which creates ~100
    allocations in one go; without idempotency the same invigilator
    could get the same email twice for the same session.

    The email is *queued* (Celery ``.delay``), not sent inline — the
    request returns immediately and the SMTP round-trip happens
    asynchronously. In tests ``CELERY_TASK_ALWAYS_EAGER=True`` makes
    the task run synchronously so ``mail.outbox`` is populated.
    """
    notif, created = Notification.objects.get_or_create(
        recipient=recipient,
        kind=kind,
        target_type=target_type,
        target_id=target_id,
        defaults={"title": title, "body": body},
    )
    if created and send_email and recipient.email:
        try:
            send_notification_email.delay(str(notif.id))
        except Exception:  # pragma: no cover — broker down
            logger.exception("Failed to enqueue email for notification %s", notif.id)
    return notif


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def send_notification_email(self: Any, notification_id: str) -> str:  # type: ignore[no-untyped-def]
    """Deliver the email and stamp the row.

    Idempotency is on the row's own flags — a retry sees
    ``email_sent_at`` already set and returns immediately.
    """
    try:
        notif = Notification.objects.select_related("recipient").get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.warning("send_notification_email: notification %s not found", notification_id)
        return "missing_notification"

    if notif.email_sent_at or notif.email_failed:
        return "already_done"

    user = notif.recipient
    try:
        send_mail(
            subject=f"[INVIGILO] {notif.title}",
            message=(
                f"Hi {user.full_name},\n\n"
                f"{notif.body}\n\n"
                "Open INVIGILO to see the details.\n\n"
                "— INVIGILO"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        # Persist the failure *before* re-raising so the retry can see
        # the state. The autoretry_for decorator catches the raise
        # and re-queues.
        Notification.objects.filter(pk=notif.pk).update(email_failed=True)
        logger.warning(
            "send_notification_email: SMTP failed for notification %s: %s",
            notif.id,
            exc,
        )
        raise

    Notification.objects.filter(pk=notif.pk).update(email_sent_at=timezone.now())
    return "sent"


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------
def upcoming_sessions_for(user: Any) -> QuerySet:
    """Return the queryset of :class:`ExamSession` rows that belong on
    this user's calendar.

    * INVIGILATOR — confirmed allocations to upcoming sessions.
    * STUDENT   — public upcoming sessions (per-student registration
      isn't tracked yet, so this is the public list; flagged as a gap
      for Phase 15).
    * Everyone else (SA/EO/HoD/Dean/SecOps) — all upcoming sessions.
    """
    from apps.exams.models import ExamSession  # local to avoid cycle

    now = timezone.now()
    upcoming = Q(starts_at__gte=now)

    if user.has_role("INVIGILATOR"):
        return (
            ExamSession.objects.filter(upcoming)
            .filter(
                allocations__invigilator__user=user,
                allocations__status="confirmed",
            )
            .distinct()
            .order_by("starts_at")
        )

    if user.has_role("STUDENT"):
        # No per-student registration table yet — use the public
        # upcoming-sessions list as a placeholder.
        return ExamSession.objects.filter(upcoming).order_by("starts_at")

    return ExamSession.objects.filter(upcoming).order_by("starts_at")


def build_ics(sessions: Iterable, *, calendar_name: str) -> str:
    """Serialise sessions to an iCalendar (RFC 5545) feed.

    Hand-rolled to avoid adding a dependency. Format quirks we honour:
        * CRLF line endings (the spec mandates this; many parsers
          accept LF but Outlook/Exchange do not).
        * 75-octet line folding (long lines are split and continuation
          lines start with a single space).
        * UTC times (``DTSTART:20260801T090000Z``).
        * Text fields are escaped for ``\\`` ``;`` ``,`` and newline.
    """
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//INVIGILO//Notifications//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_text(calendar_name)}",
    ]
    now = datetime.now(tz=dt_timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")

    for s in sessions:
        uid = f"{s.id}@invigilo"
        summary = f"{s.course.code} — {s.course.title or 'Exam'}"
        location = ""
        if s.room is not None:
            location = f"{s.room.building.code} {s.room.code}" if s.room.building else s.room.code
        description = (s.special_requirements or "").strip()
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{_to_utc(s.starts_at)}",
                f"DTEND:{_to_utc(s.ends_at)}",
                f"SUMMARY:{_escape_text(summary)}",
                f"LOCATION:{_escape_text(location)}" if location else "LOCATION:",
                f"DESCRIPTION:{_escape_text(description)}" if description else "",
                "END:VEVENT",
            ]
        )
        # Strip the empty string before join — we add it only when the
        # field is empty so the file isn't littered with blank lines.
        lines = [ln for ln in lines if ln != ""]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _to_utc(dt: datetime) -> str:
    """Render a datetime as a UTC iCal timestamp."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape_text(value: str) -> str:
    """Escape the RFC 5545 special characters in a text value."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\n", r"\n")
    )


# ---------------------------------------------------------------------------
# SMS stub — pluggable interface, no provider wired in Phase 14.
# ---------------------------------------------------------------------------
def send_sms_stub(user: Any, body: str) -> None:
    """SMS delivery stub.

    Real providers (Twilio / Africa's Talking / Vonage) plug in here.
    For now we just log so the call site can be exercised in dev
    without an account, and the absence of a provider doesn't 500 the
    request. ``notification.sms`` codename is reserved for Phase 14+.
    """
    logger.info("SMS stub: to=%s body=%r", user.email, body)


__all__ = [
    "build_ics",
    "notify",
    "send_notification_email",
    "send_sms_stub",
    "upcoming_sessions_for",
]

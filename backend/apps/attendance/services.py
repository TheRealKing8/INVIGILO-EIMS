"""Service layer for the attendance app.

Two small helpers:
  * :func:`compute_late` — given an :class:`ExamSession` and a check-in
    timestamp, return whether the attendee was late (more than 10
    minutes after the session start).
  * :func:`build_roster` — given a session, return the structured
    payload for the roster view and the CSV export (invigilator and
    student tables with present/late/expected counts).

Kept in a service module rather than the view so the CSV export and
the JSON roster share one source of truth for the data shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from django.db.models import QuerySet

from apps.allocations.models import Allocation
from apps.exams.models import ExamSession

from .models import CheckIn

# 10-minute grace window between session start and "late". Chosen to
# match the way the existing invigilation notes talk about "the chief
# takes attendance at 09:10" — 10 minutes is enough that a punctual
# invigilator who arrived at 08:59 is not flagged, but a genuinely
# late arrival is.
LATE_GRACE_MINUTES = 10


def compute_late(session: ExamSession, at: datetime) -> bool:
    """True if ``at`` is more than :data:`LATE_GRACE_MINUTES` after the session start."""
    return at > session.starts_at + timedelta(minutes=LATE_GRACE_MINUTES)


def _invigilator_expected(session: ExamSession) -> list:
    """The roster of invigilators the allocation engine wants at this session.

    Walks the session's accepted allocations and returns the
    :class:`User` objects, with a single accepted allocation per
    user (the most recent if there are multiple).
    """
    # Confirmed allocations only — drafts and rejections don't count
    # as "expected" on the day.
    accepted = (
        Allocation.objects
        .filter(session=session, status="confirmed")
        .select_related("invigilator__user")
        .order_by("invigilator__user_id", "-created_at")
    )
    seen: set = set()
    users: list = []
    for alloc in accepted:
        uid = alloc.invigilator.user_id
        if uid in seen:
            continue
        seen.add(uid)
        users.append(alloc.invigilator.user)
    return users


def _student_expected(session: ExamSession) -> int:
    """The head-count of students the exam office registered for the session."""
    return session.registered or 0


@dataclass
class RosterEntry:
    """One row in the roster view. Flat so the CSV export can render it directly."""

    user_id: str
    email: str
    full_name: str
    kind: str
    present: bool
    late: bool
    at: datetime | None
    method: str | None
    location: str
    recorded_by_email: str | None


def _entries_for_kind(
    kind: str,
    expected_users: Iterable,
    checkins: QuerySet,
) -> list[RosterEntry]:
    """Build the per-kind roster rows.

    For invigilators, ``expected_users`` is the list of users with
    accepted allocations. For students, the model doesn't track
    individual students (only the head-count), so the loop yields
    one row per *present* student with no email/name; the count
    is enough for the attendance sheet.
    """
    by_user = {c.user_id: c for c in checkins.filter(kind=kind)}
    rows: list[RosterEntry] = []
    if kind == CheckIn.Kind.INVIGILATOR:
        for u in expected_users:
            ci = by_user.get(u.id)
            rows.append(
                RosterEntry(
                    user_id=str(u.id),
                    email=u.email,
                    full_name=u.full_name,
                    kind=kind,
                    present=ci is not None,
                    late=ci.late if ci else False,
                    at=ci.at if ci else None,
                    method=ci.method if ci else None,
                    location=ci.location if ci else "",
                    recorded_by_email=ci.recorded_by.email if ci else None,
                )
            )
    else:
        # Students: rows are present attendees only; the head-count
        # sits in the totals.
        for ci in by_user.values():
            rows.append(
                RosterEntry(
                    user_id=str(ci.user_id),
                    email=ci.user.email,
                    full_name=ci.user.full_name,
                    kind=kind,
                    present=True,
                    late=ci.late,
                    at=ci.at,
                    method=ci.method,
                    location=ci.location,
                    recorded_by_email=ci.recorded_by.email,
                )
            )
    return rows


def build_roster(session: ExamSession) -> dict:
    """Return the JSON payload for the roster view + the CSV export source rows.

    The shape is::

        {
          "session": {...},
          "invigilators": [RosterEntry, ...],
          "students": [RosterEntry, ...],
          "totals": {
            "invigilator": {"present": int, "expected": int, "late": int},
            "student":     {"present": int, "expected": int, "late": int},
          }
        }
    """
    checkins = (
        CheckIn.objects
        .filter(session=session)
        .select_related("user", "recorded_by")
    )
    invigilator_users = _invigilator_expected(session)
    inv_rows = _entries_for_kind(CheckIn.Kind.INVIGILATOR, invigilator_users, checkins)
    stu_rows = _entries_for_kind(CheckIn.Kind.STUDENT, [], checkins)
    return {
        "session": {
            "id": str(session.id),
            "course_code": session.course.code,
            "course_title": session.course.title,
            "room_code": session.room.code if session.room_id else None,
            "starts_at": session.starts_at.isoformat(),
            "ends_at": session.ends_at.isoformat(),
            "status": session.status,
        },
        "invigilators": [r.__dict__ for r in inv_rows],
        "students": [r.__dict__ for r in stu_rows],
        "totals": {
            "invigilator": {
                "present": sum(1 for r in inv_rows if r.present),
                "expected": len(inv_rows),
                "late": sum(1 for r in inv_rows if r.present and r.late),
            },
            "student": {
                "present": sum(1 for r in stu_rows if r.present),
                "expected": _student_expected(session),
                "late": sum(1 for r in stu_rows if r.late),
            },
        },
    }


# CSV formula-injection guard. Any cell that starts with one of
# these characters will execute as a formula in Excel / Google
# Sheets / LibreOffice. Prefix the cell with a single quote so the
# value is read as text. (OWASP "CSV Injection" guidance.)
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: object) -> str:
    """Return ``value`` rendered as a CSV-safe string.

    None and empty strings pass through; everything else is converted
    to str, then prefixed with ``'`` if it starts with a formula
    character.
    """
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in _FORMULA_PREFIXES:
        return "'" + s
    return s


__all__ = [
    "LATE_GRACE_MINUTES",
    "RosterEntry",
    "build_roster",
    "compute_late",
    "csv_safe",
]

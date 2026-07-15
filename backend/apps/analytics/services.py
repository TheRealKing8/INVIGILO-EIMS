"""Service layer for the analytics dashboard.

The single public entry point is :func:`build_summary` — given the
requesting user, it gathers all the data the ``/dashboard/analytics``
page renders into a flat dict.

Why a single endpoint, not a fan-out (compare
:func:`apps.ai.services.build_context`)?

The dashboard home fans out because the home is built piecemeal from
many small data sources, each with its own access pattern. The
analytics page is different: it's a *one-shot* control-room view, so
we accept one extra round-trip to keep the frontend simple (no
``Promise.all`` dance, no loading state per tile, no race between
"coverage loaded" and "workload loaded"). A failed analytics request
shows one banner, not five.

Per-role scoping is applied inside the helpers — the *INVIGILATOR*
role gets a workload list filtered to their own allocations; all
other roles (operations + SA) get the org-wide view. The
:class:`apps.core.permissions.HasPermission` class-level check has
already gated the endpoint, so by the time we run these helpers we
know the caller holds ``analytics.view``.

Pattern matches :mod:`apps.ai.services` — one ``build_*`` function
broken into small private helpers, each receiving ``(user, period)``
so it can scope its own query.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

from django.db.models import Count, Q
from django.db.models.functions import TruncWeek
from django.utils import timezone

from apps.allocations.models import Allocation, AllocationRun
from apps.attendance.models import CheckIn
from apps.exams.models import ExamPeriod, ExamSession
from apps.incidents.models import Incident
from apps.invigilators.models import InvigilatorProfile


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------
@dataclass
class AnalyticsContext:
    """Live facts the analytics page cites. Every field is computed
    lazily by the helpers below so a caller that only reads
    ``coverage`` doesn't pay for the workload query.
    """

    period: Optional[ExamPeriod]
    coverage: Optional[float]
    upcoming_sessions_count: int
    checkins_today: int
    late_count_today: int
    open_incidents_count: int
    invigilator_workload: list[dict]
    attendance_trend: list[dict]
    sessions_by_day: list[dict]
    incidents_by_severity: dict
    generated_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _active_period() -> Optional[ExamPeriod]:
    return ExamPeriod.objects.filter(is_active=True).order_by("-starts_on").first()


def _coverage(period: Optional[ExamPeriod]) -> Optional[float]:
    """Latest allocation run's capacity utilisation as a percentage.

    Returns ``None`` when there are no runs yet (fresh period, no
    engine output) so the frontend can render "—" rather than
    "0%". Capacity utilisation is a 0–1 fraction in
    :class:`AllocationRun`; we multiply by 100 here so the
    frontend doesn't have to.
    """
    if period is None:
        return None
    latest = AllocationRun.objects.filter(period=period).order_by("-created_at", "-id").first()
    if latest is None:
        return None
    return float(latest.capacity_utilisation) * 100


def _upcoming_sessions_count(period: Optional[ExamPeriod]) -> int:
    if period is None:
        return 0
    now = timezone.now()
    return ExamSession.objects.filter(
        period=period, starts_at__gte=now
    ).count()


def _checkins_today() -> tuple[int, int]:
    """Return ``(checkins_today, late_count_today)`` in one query pair.

    Two counts so we don't pay for two SQL round-trips. ``late`` is
    a boolean on :class:`CheckIn` (Phase 13) — true if the check-in
    landed outside the 10-minute grace window.
    """
    cutoff = timezone.now() - timedelta(hours=24)
    base = CheckIn.objects.filter(created_at__gte=cutoff)
    total = base.count()
    late = base.filter(late=True).count()
    return total, late


def _open_incidents_count(period: Optional[ExamPeriod]) -> int:
    """Open + investigating + escalated incidents in the active period.

    ``resolved`` is excluded so the count tracks work the field
    still has to do. When there's no active period, count across
    all periods (so the home page KPI is never artificially zero).
    """
    open_statuses = ["open", "investigating", "escalated"]
    qs = Incident.objects.filter(status__in=open_statuses)
    if period is not None:
        qs = qs.filter(session__period=period)
    return qs.count()


def _invigilator_workload(user: Any, period: Optional[ExamPeriod], limit: int = 5) -> list[dict]:
    """Top ``limit`` invigilators by allocation count in the active period.

    For the ``INVIGILATOR`` role, filter to *their own* allocations
    so the list isn't a mirror of the org-wide view they can't act
    on. Operations roles see the whole pool.

    Shape per row::

        {
            "invigilator_id": str,
            "name": str,
            "email": str,
            "allocated": int,
            "max_per_cycle": int,
            "fill_pct": int,         # 0..100
        }
    """
    if period is None:
        return []
    alloc_qs = Allocation.objects.filter(
        run__period=period,
        invigilator__is_active=True,
        invigilator__user__is_active=True,
    )
    if user.has_role("INVIGILATOR") and not user.has_role("EXAMINATION_OFFICER") \
            and not user.has_role("SYSTEM_ADMINISTRATOR") \
            and not user.has_role("HEAD_OF_DEPARTMENT") \
            and not user.has_role("FACULTY_DEAN"):
        alloc_qs = alloc_qs.filter(invigilator__user=user)

    rows = (
        alloc_qs
        .values("invigilator_id", "invigilator__user__full_name", "invigilator__user__email",
                "invigilator__max_sessions_per_cycle")
        .annotate(allocated=Count("id"))
        .order_by("-allocated", "invigilator__user__full_name")[:limit]
    )
    out: list[dict] = []
    for r in rows:
        max_per = r["invigilator__max_sessions_per_cycle"] or 0
        allocated = r["allocated"]
        fill = round((allocated / max_per) * 100, 1) if max_per else 0
        out.append({
            "invigilator_id": str(r["invigilator_id"]),
            "name": r["invigilator__user__full_name"] or r["invigilator__user__email"] or "—",
            "email": r["invigilator__user__email"] or "",
            "allocated": allocated,
            "max_per_cycle": max_per,
            "fill_pct": fill,
        })
    return out


def _attendance_trend(weeks: int = 12) -> list[dict]:
    """Weekly check-in counts ending the current ISO week.

    Returns ``weeks`` buckets, oldest first, latest is the current
    week. Each row is ``{"week_start": "YYYY-MM-DD", "count": int}``.
    Buckets with zero check-ins are included so the sparkline
    doesn't have gaps.
    """
    # Anchor to the start of the current ISO week (Monday).
    today = timezone.now().date()
    current_week_start = today - timedelta(days=today.weekday())
    earliest = current_week_start - timedelta(weeks=weeks - 1)

    raw = (
        CheckIn.objects
        .filter(created_at__date__gte=earliest)
        .annotate(week=TruncWeek("created_at"))
        .values("week")
        .annotate(count=Count("id"))
        .order_by("week")
    )
    by_week: dict[date, int] = {}
    for row in raw:
        # ``TruncWeek`` returns a datetime; convert to the date of
        # that bucket's Monday so the JSON is a plain ``YYYY-MM-DD``.
        w = row["week"]
        by_week[w.date() if hasattr(w, "date") else w] = row["count"]

    out: list[dict] = []
    for offset in range(weeks):
        week_start = earliest + timedelta(weeks=offset)
        out.append({
            "week_start": week_start.isoformat(),
            "count": by_week.get(week_start, 0),
        })
    return out


def _sessions_by_day(period: Optional[ExamPeriod], days: int = 7) -> list[dict]:
    """Next ``days`` days of sessions in the active period, grouped by date.

    Each row::

        {
            "date": "YYYY-MM-DD",
            "count": int,
            "courses": [str, ...]      # up to 3 course codes
        }

    The course-code list is capped at 3 to keep the right-rail card
    compact — the count and date are the headline numbers.
    """
    if period is None:
        return []
    now = timezone.now()
    end = now + timedelta(days=days)
    qs = (
        ExamSession.objects
        .filter(period=period, starts_at__gte=now, starts_at__lt=end)
        .select_related("course")
        .order_by("starts_at")
    )
    by_day: dict[date, list[str]] = {}
    for s in qs:
        d = s.starts_at.date()
        by_day.setdefault(d, []).append(s.course.code)
    out: list[dict] = []
    for offset in range(days):
        d = (now + timedelta(days=offset)).date()
        codes = by_day.get(d, [])
        out.append({
            "date": d.isoformat(),
            "count": len(codes),
            "courses": codes[:3],
        })
    return out


def _incidents_by_severity(period: Optional[ExamPeriod]) -> dict[str, int]:
    """Counts of incidents per severity in the active period.

    All four severity levels are always present in the response
    (zero-filled) so the frontend can render chips for all of
    them without conditionals.
    """
    base = Incident.objects.all()
    if period is not None:
        base = base.filter(session__period=period)
    rows = base.values("severity").annotate(count=Count("id"))
    counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for r in rows:
        if r["severity"] in counts:
            counts[r["severity"]] = r["count"]
    return counts


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def build_summary(user: Any) -> AnalyticsContext:
    """Return the full analytics snapshot for the given user.

    Order matters: ``_active_period()`` runs first so the helpers
    below can share the result without re-hitting the DB. The
    period is None when no period is active; helpers degrade
    gracefully (returning None / 0 / []).
    """
    period = _active_period()
    total, late = _checkins_today()
    return AnalyticsContext(
        period=period,
        coverage=_coverage(period),
        upcoming_sessions_count=_upcoming_sessions_count(period),
        checkins_today=total,
        late_count_today=late,
        open_incidents_count=_open_incidents_count(period),
        invigilator_workload=_invigilator_workload(user, period),
        attendance_trend=_attendance_trend(),
        sessions_by_day=_sessions_by_day(period),
        incidents_by_severity=_incidents_by_severity(period),
        generated_at=timezone.now(),
    )


__all__ = ["AnalyticsContext", "build_summary"]

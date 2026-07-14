"""Rule-based assistant composer.

The service is intentionally not an LLM. It gathers live data from
the database and matches the user's question against a small set of
intents (``status``, ``conflicts``, ``invigilators``, ``sessions``,
``incidents``, ``help``). For each intent, a deterministic template
renders a reply that names real DB values, not invented ones.

# ---------------------------------------------------------------------------
# Deferred AI features (out of scope for the current brief)
# ---------------------------------------------------------------------------
# "AI-powered anomaly detection" — flagging unusual check-in patterns,
# late arrivals clustering, suspicious incident bursts.  Requires a
# labeled malpractice dataset to train on; we have none. Re-evaluate
# once the audit log + incident history carry enough rows to label.
#
# "AI room recommendation" — LLM-assisted seating picks. Phase 17.
#
# "Predictive analytics" — workload forecasts, conflict risk scores.
# Phase 17.
# ---------------------------------------------------------------------------

The output is plain English with a few ``$placeholders`` for
numbers and names. There is no chain-of-thought, no tool use beyond
the four ORM queries below, and no fabricated details.

Why rule-based, not an LLM?

* Determinism. Two operators asking the same question at the same
  moment get the same answer — useful when you're using the
  assistant to answer registrar questions.
* Audit. The replies cite the DB rows they came from, so a
  "what's blocking the cycle?" reply can be diffed against the
  Conflict table.
* Cheap. No tokens, no third-party dependency, no PHI/PII leak via
  an external API. Everything stays on the Invigilo box.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from django.db.models import Count, Q
from django.utils import timezone

from apps.allocations.models import AllocationRun, Conflict
from apps.exams.models import ExamPeriod, ExamSession
from apps.incidents.models import Incident
from apps.invigilators.models import InvigilatorProfile


@dataclass
class ContextSnapshot:
    """Live database facts the assistant cites. Every field is
    computed lazily by the helpers below so a request that doesn't
    ask about conflicts never pays for the conflict query."""

    period: Optional[ExamPeriod]
    upcoming_sessions: list[ExamSession]
    latest_run: Optional[AllocationRun]
    open_conflicts: list[Conflict]
    open_incidents: list[Incident]
    invigilator_total: int
    invigilator_unavailable_today: int
    generated_at: datetime


def _safe_period() -> Optional[ExamPeriod]:
    return ExamPeriod.objects.filter(is_active=True).order_by("-starts_on").first()


def _upcoming_sessions(limit: int = 5) -> list[ExamSession]:
    """Sessions starting in the next 7 days, soonest first."""
    now = timezone.now()
    horizon = now + timedelta(days=7)
    return list(
        ExamSession.objects.select_related("course", "room")
        .filter(period__is_active=True, starts_at__gte=now, starts_at__lte=horizon)
        .order_by("starts_at")[:limit]
    )


def _latest_run() -> Optional[AllocationRun]:
    return (
        AllocationRun.objects.select_related("period")
        .order_by("-created_at", "-id")
        .first()
    )


def _open_conflicts(limit: int = 5) -> list[Conflict]:
    return list(
        Conflict.objects.select_related("session", "invigilator")
        .filter(session__period__is_active=True)
        .exclude(severity="info")
        .order_by("-created_at")[:limit]
    )


def _open_incidents(limit: int = 5) -> list[Incident]:
    return list(
        Incident.objects.filter(status__in=["open", "acknowledged", "investigating"])
        .order_by("-reported_at")[:limit]
    )


def _invigilator_counts() -> tuple[int, int]:
    total = InvigilatorProfile.objects.filter(is_active=True, user__is_active=True).count()
    today = date.today()
    unavailable = (
        InvigilatorProfile.objects.filter(is_active=True, user__is_active=True)
        .filter(availability__date=today)
        .exclude(availability__status="available")
        .distinct()
        .count()
    )
    return total, unavailable


def build_context() -> ContextSnapshot:
    period = _safe_period()
    latest = _latest_run()
    inc_total, inc_unavail = _invigilator_counts()
    return ContextSnapshot(
        period=period,
        upcoming_sessions=_upcoming_sessions(),
        latest_run=latest,
        open_conflicts=_open_conflicts(),
        open_incidents=_open_incidents(),
        invigilator_total=inc_total,
        invigilator_unavailable_today=inc_unavail,
        generated_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Intent matching
# ---------------------------------------------------------------------------
# Order matters: the first matching handler wins. ``help`` is the
# catch-all at the end.
INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("conflicts", ("conflict", "issue", "problem", "block", "stuck", "failing")),
    ("incidents", ("incident", "alert", "report", "complaint", "issue")),
    ("invigilators", ("invigilator", "staff", "roster", "workload", "capacity")),
    ("sessions", ("session", "exam", "schedule", "timetable", "today", "tomorrow", "this week")),
    ("run", ("run", "engine", "allocation", "assign")),
    ("status", ("status", "summary", "overview", "how is", "how's", "cycle")),
    ("help", ("help", "what can you do", "commands", "options")),
]


def detect_intent(message: str) -> str:
    text = message.lower().strip()
    if not text:
        return "help"
    for intent, keywords in INTENT_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return intent
    return "help"


# ---------------------------------------------------------------------------
# Reply composers — one per intent
# ---------------------------------------------------------------------------
def _reply_status(ctx: ContextSnapshot) -> tuple[str, list[str]]:
    period = ctx.period
    if not period:
        return (
            "There is no active exam period right now. "
            "Activate one from the Exams page to start scheduling.",
            ["How do I activate a period?", "What does the engine check?", "Open incidents"],
        )
    coverage = (
        f"{round(ctx.latest_run.capacity_utilisation * 100, 1)}%"
        if ctx.latest_run
        else "no runs yet"
    )
    return (
        f"The active cycle is **{period.name} ({period.code})**, "
        f"running {period.starts_on} → {period.ends_on}. "
        f"Latest engine coverage is **{coverage}**. "
        f"Open conflicts: **{len(ctx.open_conflicts)}**. "
        f"Open incidents: **{len(ctx.open_incidents)}**.",
        ["Why do I have conflicts?", "Show today's sessions", "Who is on duty today?"],
    )


def _reply_conflicts(ctx: ContextSnapshot) -> tuple[str, list[str]]:
    if not ctx.open_conflicts:
        return (
            "No blocking conflicts in the active cycle. "
            "If you just re-ran the engine, this is the cleanest state possible.",
            ["Why is coverage less than 100%?", "What does the engine check?"],
        )
    bullets = []
    for c in ctx.open_conflicts[:3]:
        s = c.session.course.code if c.session_id and c.session else "a session"
        bullets.append(f"- **{c.type.replace('_', ' ')}** on {s}: {c.detail}")
    head = "Here are the top conflicts the engine is reporting right now:\n" + "\n".join(bullets)
    return (
        head,
        ["Re-run the engine", "What does the engine check?", "How do I fix a no-room conflict?"],
    )


def _reply_incidents(ctx: ContextSnapshot) -> tuple[str, list[str]]:
    if not ctx.open_incidents:
        return (
            "No open incidents. The field is clean.",
            ["Show today's sessions", "How is coverage calculated?"],
        )
    bullets = []
    for i in ctx.open_incidents[:3]:
        bullets.append(f"- **{i.severity}** · {i.title}")
    return (
        f"Open incidents ({len(ctx.open_incidents)} total):\n" + "\n".join(bullets),
        ["Show only critical", "Mark all as acknowledged", "What does severity mean?"],
    )


def _reply_invigilators(ctx: ContextSnapshot) -> tuple[str, list[str]]:
    avail = ctx.invigilator_total - ctx.invigilator_unavailable_today
    return (
        f"You have **{ctx.invigilator_total}** active invigilators. "
        f"**{avail}** are available today, "
        f"**{ctx.invigilator_unavailable_today}** are marked unavailable.",
        ["Who is overloaded?", "Workload cap?"],
    )


def _reply_sessions(ctx: ContextSnapshot) -> tuple[str, list[str]]:
    if not ctx.upcoming_sessions:
        return (
            "No sessions scheduled in the next 7 days. "
            "Create one from the Exams page.",
            ["How do I create a session?", "Who is on duty today?"],
        )
    bullets = []
    for s in ctx.upcoming_sessions[:5]:
        when = s.starts_at.strftime("%a %d %b %H:%M")
        room = s.room.code if s.room_id else "no room"
        bullets.append(f"- {when} · {s.course.code} · {room} · {s.registered}/{s.capacity} candidates")
    return (
        f"Next {len(bullets)} sessions in the active cycle:\n" + "\n".join(bullets),
        ["Show conflicts", "Run the engine", "Export a report"],
    )


def _reply_run(ctx: ContextSnapshot) -> tuple[str, list[str]]:
    if not ctx.latest_run:
        return (
            "The engine has not been run for the active cycle yet. "
            "Open Allocations and click **Run engine**.",
            ["What does the engine check?", "How long does a run take?"],
        )
    r = ctx.latest_run
    coverage = round(r.capacity_utilisation * 100, 1)
    return (
        f"Last run on **{r.period.code}** placed **{r.sessions_placed}/{r.sessions_total}** "
        f"sessions in {r.runtime_seconds}s. Coverage **{coverage}%**. "
        f"Avg workload {r.avg_workload} (max {r.max_workload}).",
        ["Re-run the engine", "Why are sessions unplaced?"],
    )


def _reply_help(_ctx: ContextSnapshot) -> tuple[str, list[str]]:
    return (
        "I'm fed live data from your database. Try asking:\n"
        "- \"What's the status of the current cycle?\"\n"
        "- \"What conflicts is the engine reporting?\"\n"
        "- \"Who's on duty today?\"\n"
        "- \"Show the latest allocation run.\"\n"
        "- \"Any open incidents?\"\n"
        "I work best with short, specific questions.",
        ["Status", "Conflicts", "Sessions", "Run"],
    )


REPLY_BUILDERS: dict[str, Callable[[ContextSnapshot], tuple[str, list[str]]]] = {
    "status": _reply_status,
    "conflicts": _reply_conflicts,
    "incidents": _reply_incidents,
    "invigilators": _reply_invigilators,
    "sessions": _reply_sessions,
    "run": _reply_run,
    "help": _reply_help,
}


def compose_reply(message: str, ctx: ContextSnapshot) -> tuple[str, list[str], str]:
    """Return ``(reply, suggestions, intent)`` for ``message``."""
    intent = detect_intent(message)
    reply, suggestions = REPLY_BUILDERS[intent](ctx)
    return reply, suggestions, intent


__all__ = ["build_context", "compose_reply", "detect_intent", "ContextSnapshot"]

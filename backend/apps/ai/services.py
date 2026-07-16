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

# ---------------------------------------------------------------------------
# Phase 19 — LLM fallback path
# ---------------------------------------------------------------------------
# When ``settings.OPENROUTER_API_KEY`` is set, the view layer routes
# the question to :func:`compose_reply_llm` instead, which uses the
# same :func:`build_context` snapshot as the source of truth and
# hands the natural-language rendering to OpenRouter. The rule-based
# path remains as the fallback (and the default in dev when no key
# is configured).
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


# ---------------------------------------------------------------------------
# Phase 19 — LLM path
# ---------------------------------------------------------------------------
import json
import logging
import re
from typing import Iterable

from django.conf import settings

from .openrouter import OpenRouterError, chat
from .prompts import SYSTEM_PROMPT, build_user_prompt


logger = logging.getLogger("invigilo.ai")


def build_messages(role: str, message: str, ctx: ContextSnapshot) -> list[dict]:
    """Build the OpenAI-shaped message list for an LLM call.

    Shared by the non-streaming :func:`compose_reply_llm` (HTTP
    view) and the streaming path in
    :mod:`apps.realtime.views` (SSE view). One source of truth for
    the wire shape — both callers produce the same
    ``[system, user]`` list, so an LLM-side change to the system
    prompt is picked up everywhere in one place.

    The user-role message is the :func:`build_user_prompt` output
    (role label + question + fenced-JSON context), which is itself
    a defence against prompt injection: the LLM treats the JSON
    block as data, not as instructions.
    """
    context_dict = _context_to_dict(ctx)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(role, message, context_dict)},
    ]


def _user_role_code(user) -> str:
    """Best-effort role code for the system prompt.

    Falls back to ``"USER"`` when the user has no primary role
    (e.g. a brand-new registration that hasn't been assigned yet,
    or a service account). The LLM treats unknown roles as
    read-only by default — see ``SYSTEM_PROMPT``.
    """
    try:
        primary = user.primary_role_code
    except AttributeError:
        primary = None
    if primary:
        return primary
    # Superusers get a clearer label even without an explicit role.
    if getattr(user, "is_superuser", False):
        return "SYSTEM_ADMINISTRATOR"
    return "GUEST"


def _context_to_dict(ctx: ContextSnapshot) -> dict:
    """Plain dict the LLM sees. Mirrors the smaller ``_context_to_dict``
    in views.py but includes a few more fields (run stats) that are
    useful for the LLM but would bloat the chat-panel disclosure.
    """
    return {
        "active_period": ctx.period.code if ctx.period else None,
        "active_period_name": ctx.period.name if ctx.period else None,
        "active_period_window": (
            f"{ctx.period.starts_on} → {ctx.period.ends_on}" if ctx.period else None
        ),
        "upcoming_sessions": [
            {
                "course": s.course.code if s.course_id else None,
                "room": s.room.code if s.room_id else None,
                "starts_at": s.starts_at.isoformat() if s.starts_at else None,
                "registered": s.registered,
                "capacity": s.capacity,
            }
            for s in ctx.upcoming_sessions[:5]
        ],
        "open_conflicts": [
            {
                "type": c.type,
                "severity": c.severity,
                "detail": c.detail,
            }
            for c in ctx.open_conflicts[:5]
        ],
        "open_incidents": [
            {
                "severity": i.severity,
                "title": i.title,
            }
            for i in ctx.open_incidents[:5]
        ],
        "invigilator_total": ctx.invigilator_total,
        "invigilator_unavailable_today": ctx.invigilator_unavailable_today,
        "latest_run": (
            {
                "period": ctx.latest_run.period.code if ctx.latest_run.period_id else None,
                "coverage_pct": (
                    round(ctx.latest_run.capacity_utilisation * 100, 1)
                    if ctx.latest_run and ctx.latest_run.capacity_utilisation is not None
                    else None
                ),
                "sessions_placed": ctx.latest_run.sessions_placed if ctx.latest_run else None,
                "sessions_total": ctx.latest_run.sessions_total if ctx.latest_run else None,
            }
            if ctx.latest_run
            else None
        ),
    }


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_LOOSE_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_llm_json(content: str) -> tuple[str, list[str]]:
    """Extract ``{"reply": "...", "suggestions": [...]}`` from the LLM output.

    The system prompt asks for raw JSON. Defensive parsing handles the
    three realistic failure modes:

    1. Perfect: parse the first JSON object.
    2. Wrapped: the model wrapped the JSON in ```json fences — strip them.
    3. Sloppy: there's a stray sentence before/after — fall back to the
       first ``{...}`` block. If the result still doesn't parse, treat
       the entire content as the reply with empty suggestions.
    """
    content = (content or "").strip()
    # 1) wrapped in code fences
    m = _JSON_FENCE_RE.search(content)
    if m:
        candidate = m.group(1)
    else:
        # 2) bare JSON object somewhere in the content
        m = _LOOSE_JSON_RE.search(content)
        candidate = m.group(0) if m else content
    try:
        data = json.loads(candidate)
    except ValueError:
        logger.warning("llm reply was not JSON; using as plain text")
        return content, []
    reply = (data.get("reply") or "").strip()
    raw_suggestions = data.get("suggestions") or []
    if not isinstance(raw_suggestions, list):
        raw_suggestions = []
    suggestions = [str(s).strip() for s in raw_suggestions if str(s).strip()][:4]
    return reply, suggestions


async def compose_reply_llm(
    user,
    message: str,
    ctx: ContextSnapshot,
    role: str | None = None,
) -> tuple[str, list[str], str, dict]:
    """Call OpenRouter with the live context and return a reply.

    Returns ``(reply, suggestions, intent, llm_meta)`` where
    ``llm_meta`` is a dict the view can log (model, latency, token
    counts). ``intent`` is always ``"llm"`` for the LLM path —
    there's no intent classifier in front of the LLM, the LLM
    itself decides what to do.

    ``role`` is computed by the caller (the view). It MUST be passed
    in: doing the role lookup inside the async function trips
    Django's sync-only-ORM check.
    """
    if not role:
        role = _user_role_code(user)
    messages = build_messages(role=role, message=message, ctx=ctx)

    result = await chat(messages=messages)
    reply, suggestions = _parse_llm_json(result.content)
    llm_meta = {
        "model": result.model,
        "latency_ms": result.latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }
    return reply, suggestions, "llm", llm_meta


__all__ = [
    "build_context",
    "build_messages",
    "compose_reply",
    "compose_reply_llm",
    "detect_intent",
    "ContextSnapshot",
]

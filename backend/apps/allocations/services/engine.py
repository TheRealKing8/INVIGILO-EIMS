"""Allocation engine.

The engine assigns invigilators to exam sessions while respecting a small
set of hard constraints. It is intentionally a **deterministic greedy**,
not an LP solver — for a typical exam period (a few hundred sessions
across a few hundred invigilators) the greedy pass reaches the same
solution in well under a second, which keeps the UI's "Run engine"
button snappy. The tradeoff is that for adversarial inputs (many
overlapping sessions, very small invigilator pool) the greedy may
produce infeasible runs; the fallback pass below relaxes department
mixing to claw back coverage.

Constraints
-----------
1. **Workload cap.** Each invigilator has ``max_sessions_per_cycle``;
   the engine never exceeds it.
2. **No double-booking.** One invigilator is never in two sessions
   whose time windows overlap.
3. **Department mixing.** No two invigilators in the same session may
   come from the same department (exams are invigilated
   cross-departmentally).
4. **Status filter.** Only invigilators with no ``Availability`` row
   for the session's date in a non-available status are eligible.
5. **Room capacity.** The session's existing room is reused; the
   engine does not re-allocate rooms.
6. **Coverage floor.** At least ``invigilators_required`` invigilators
   per session (the session is left under-staffed with a ``Conflict``
   row if the pool is exhausted).

Algorithm
---------
Pass 1 (constrained) — order sessions by ``(registered desc,
len(eligible) asc)`` (most-constrained first), and assign invigilators
in order of least-current-workload. Skip any candidate that would
violate a constraint. A session that still has < required after pass 1
is recorded as a ``Conflict`` (type ``no_eligible_invigilators`` or
``workload_cap``).

Pass 2 (relax dept-mix) — re-attempt any session still under-staffed,
ignoring the dept-mix constraint.

Returns
-------
:func:`run_engine` writes the rows to the DB and returns the run
id plus a summary dict. The HTTP layer (``views.py``) wraps it.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.exams.models import ExamPeriod, ExamSession
from apps.invigilators.models import Availability, InvigilatorProfile

from apps.allocations.models import Allocation, AllocationRun, Conflict


logger = logging.getLogger("invigilo.allocations")


# ---------------------------------------------------------------------------
# Working data — pure Python, no DB, so the engine is easy to test in
# isolation. (Production goes through the DB.)
# ---------------------------------------------------------------------------
@dataclass
class _Candidate:
    profile: InvigilatorProfile
    department_id: Optional[str]
    max_sessions: int
    unavailable_dates: set[date] = field(default_factory=set)


@dataclass
class _Session:
    obj: ExamSession
    required: int
    eligible: list[_Candidate] = field(default_factory=list)
    chosen: list[_Candidate] = field(default_factory=list)
    departments_in_session: set[str] = field(default_factory=set)

    def overlaps(self, other: "_Session") -> bool:
        return self.obj.starts_at < other.obj.ends_at and other.obj.starts_at < self.obj.ends_at


@dataclass
class _PassResult:
    conflicts: list[Conflict]
    placed_slots: int
    total_required: int
    max_workload: int
    avg_workload: float


# ---------------------------------------------------------------------------
# Pre-compute the candidate pool for a period.
# ---------------------------------------------------------------------------
def _build_candidates(period: ExamPeriod) -> list[_Candidate]:
    """Return all profiles that *might* be eligible for any session in the period.

    Unavailability is per-date and checked against each session when we
    iterate, not pre-filtered.
    """
    candidates: list[_Candidate] = []
    qs = InvigilatorProfile.objects.select_related("user", "primary_department").filter(
        is_active=True, user__is_active=True
    )
    for profile in qs:
        unavail = set(
            Availability.objects.filter(
                invigilator=profile,
                date__gte=period.starts_on,
                date__lte=period.ends_on,
            )
            .exclude(status="available")
            .values_list("date", flat=True)
        )
        candidates.append(
            _Candidate(
                profile=profile,
                department_id=str(profile.primary_department_id)
                if profile.primary_department_id
                else None,
                max_sessions=profile.max_sessions_per_cycle,
                unavailable_dates=unavail,
            )
        )
    return candidates


def _build_sessions(period: ExamPeriod, candidates: list[_Candidate]) -> list[_Session]:
    """Order sessions and stamp each one with its initially-eligible set."""
    sessions_qs = (
        ExamSession.objects.select_related("course", "room", "room__building")
        .filter(period=period)
        .order_by("-registered", "starts_at")
    )
    out: list[_Session] = []
    for s in sessions_qs:
        required = max(1, s.invigilators_required or 1)
        eligible = [c for c in candidates if s.starts_at.date() not in c.unavailable_dates]
        out.append(_Session(obj=s, required=required, eligible=eligible))
    return out


# ---------------------------------------------------------------------------
# Per-session placement
# ---------------------------------------------------------------------------
def _overlaps_with_chosen(candidate: _Candidate, sess: _Session, all_chosen: dict[int, list[_Session]]) -> bool:
    """True if ``candidate`` is already assigned to a session that overlaps ``sess``."""
    return any(sess.overlaps(other) for other in all_chosen.get(candidate.profile.pk, []))


def _same_dept(candidate: _Candidate, sess: _Session) -> bool:
    if candidate.department_id is None:
        return False
    return candidate.department_id in sess.departments_in_session


def _assign_pass(
    sessions: list[_Session],
    workload: dict[int, int],
    chosen_index: dict[int, list[_Session]],
    *,
    enforce_dept_mix: bool,
) -> _PassResult:
    """One pass of the greedy. Mutates ``sessions`` in place."""
    conflicts: list[Conflict] = []
    placed_slots = 0
    max_workload = 0
    total_required = sum(s.required for s in sessions)

    for sess in sessions:
        while len(sess.chosen) < sess.required:
            # Sort candidates by least-current-workload; break ties on dept-diversity.
            candidates = sorted(
                sess.eligible,
                key=lambda c: (
                    workload.get(c.profile.pk, 0),
                    0 if c.department_id and c.department_id not in sess.departments_in_session else 1,
                ),
            )
            picked = None
            for cand in candidates:
                if any(c.profile.pk == cand.profile.pk for c in sess.chosen):
                    continue
                if workload.get(cand.profile.pk, 0) >= cand.max_sessions:
                    continue
                if _overlaps_with_chosen(cand, sess, chosen_index):
                    continue
                if enforce_dept_mix and _same_dept(cand, sess):
                    continue
                picked = cand
                break

            if picked is None:
                # Couldn't fill this slot.
                candidate_for_conflict = sess.eligible[0] if sess.eligible else None
                conflicts.append(
                    Conflict(
                        run=None,  # filled in after the run row is saved
                        type="no_eligible_invigilators" if not sess.eligible else "workload_cap",
                        severity="error",
                        detail=(
                            f"Session {sess.obj.course.code} @ {sess.obj.starts_at:%Y-%m-%d %H:%M} "
                            f"has {len(sess.chosen)}/{sess.required} invigilators assigned."
                        ),
                        session=sess.obj,
                        invigilator=candidate_for_conflict.profile if candidate_for_conflict else None,
                    )
                )
                break

            sess.chosen.append(picked)
            sess.departments_in_session.add(picked.department_id or "")
            workload[picked.profile.pk] = workload.get(picked.profile.pk, 0) + 1
            chosen_index.setdefault(picked.profile.pk, []).append(sess)
            placed_slots += 1
            max_workload = max(max_workload, workload[picked.profile.pk])

    if workload:
        avg_workload = sum(workload.values()) / len(workload)
    else:
        avg_workload = 0.0

    return _PassResult(
        conflicts=conflicts,
        placed_slots=placed_slots,
        total_required=total_required,
        max_workload=max_workload,
        avg_workload=avg_workload,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
@transaction.atomic
def run_engine(period: ExamPeriod, *, triggered_by=None) -> AllocationRun:
    """Run the engine against ``period``. Returns the persisted :class:`AllocationRun`."""
    started = time.monotonic()
    candidates = _build_candidates(period)
    sessions = _build_sessions(period, candidates)
    workload: dict[int, int] = {}
    chosen_index: dict[int, list[_Session]] = {}

    # Pass 1: constrained (honours dept-mix).
    pass1 = _assign_pass(sessions, workload, chosen_index, enforce_dept_mix=True)

    # Pass 2: relax dept-mix for sessions still under-staffed.
    still_under = [s for s in sessions if len(s.chosen) < s.required]
    pass2 = _PassResult(conflicts=[], placed_slots=0, total_required=0, max_workload=0, avg_workload=0.0)
    if still_under:
        pass2 = _assign_pass(still_under, workload, chosen_index, enforce_dept_mix=False)

    # Persist.
    placed_slots = pass1.placed_slots + pass2.placed_slots
    total_required = pass1.total_required
    sessions_placed = sum(1 for s in sessions if len(s.chosen) >= s.required)
    avg_workload = round(sum(workload.values()) / len(workload), 2) if workload else 0
    max_workload = max(workload.values()) if workload else 0
    capacity_utilisation = round(placed_slots / total_required, 4) if total_required else 0

    run = AllocationRun.objects.create(
        period=period,
        triggered_by=triggered_by,
        sessions_total=total_required,
        sessions_placed=sessions_placed,
        avg_workload=avg_workload,
        max_workload=max_workload,
        capacity_utilisation=capacity_utilisation,
        runtime_seconds=int(time.monotonic() - started),
        finished_at=timezone.now(),
    )

    allocations = [
        Allocation(
            run=run,
            session=sess.obj,
            invigilator=cand.profile,
            room=sess.obj.room,
            role="invigilator",
            status="draft",
        )
        for sess in sessions
        for cand in sess.chosen
    ]
    Allocation.objects.bulk_create(allocations)

    # Stamp the conflicts with the freshly-saved run, then persist.
    for c in pass1.conflicts + pass2.conflicts:
        c.run = run
    Conflict.objects.bulk_create(pass1.conflicts + pass2.conflicts)

    return run


__all__ = ["run_engine"]

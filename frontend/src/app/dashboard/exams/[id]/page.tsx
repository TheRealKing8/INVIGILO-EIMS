/**
 * Exam session detail — drill-in from the /dashboard/exams table.
 *
 * Shows the full session record, the assigned invigilators (from the
 * latest run), any related incidents, and a row of lifecycle action
 * buttons (Publish / Draft / Cancel / Reschedule). The action handlers
 * mirror the parent page's behaviour: the backend enforces which
 * transitions are legal, and a 409 surfaces a friendly banner here.
 *
 * The "Back to examinations" link is the only navigation out; the
 * lifecycle buttons stay on the page after success so the user can
 * re-read the new status without bouncing back to the list.
 */
"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { ProgressBar } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  cancelExamSession,
  draftExamSession,
  getAllocationForSession,
  getExamSession,
  getIncidentsForSession,
  publishExamSession,
  rescheduleExamSession,
  type Allocation,
  type ExamSession,
  type Incident,
  type Paginated,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

const statusTone: Record<
  ExamSession["status"],
  { tone: "brand" | "success" | "warning" | "neutral" | "danger"; label: string }
> = {
  draft: { tone: "neutral", label: "Draft" },
  scheduled: { tone: "brand", label: "Scheduled" },
  ready: { tone: "success", label: "Ready" },
  in_progress: { tone: "warning", label: "In progress" },
  pending: { tone: "warning", label: "Pending" },
  completed: { tone: "neutral", label: "Completed" },
  cancelled: { tone: "danger", label: "Cancelled" },
};

const incidentSeverityTone: Record<
  Incident["severity"],
  "neutral" | "warning" | "danger" | "info"
> = {
  low: "neutral",
  medium: "warning",
  high: "danger",
  critical: "info",
};

const incidentStatusTone: Record<
  Incident["status"],
  "danger" | "warning" | "success" | "brand"
> = {
  open: "danger",
  investigating: "warning",
  escalated: "warning",
  resolved: "success",
};

const allocationStatusTone: Record<
  Allocation["status"],
  "success" | "warning" | "danger"
> = {
  confirmed: "success",
  draft: "warning",
  rejected: "danger",
};

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "2-digit",
  });
}
function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
function fmtDuration(min: number | null | undefined): string {
  if (min == null) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

function initialsOf(name: string | undefined): string {
  if (!name) return "??";
  return name
    .split(/\s+/)
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function availableActions(status: ExamSession["status"]): Array<{
  key: "cancel" | "draft" | "publish" | "reschedule";
  label: string;
  tone: "danger" | "ghost" | "primary";
}> {
  switch (status) {
    case "draft":
      return [{ key: "publish", label: "Publish", tone: "primary" }];
    case "scheduled":
      return [
        { key: "draft", label: "Move to draft", tone: "ghost" },
        { key: "cancel", label: "Cancel", tone: "danger" },
      ];
    case "pending":
      return [
        { key: "publish", label: "Publish", tone: "primary" },
        { key: "cancel", label: "Cancel", tone: "danger" },
      ];
    case "ready":
      return [{ key: "cancel", label: "Cancel", tone: "danger" }];
    default:
      return [];
  }
}

export default function ExamSessionDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const { data, isLoading, error, refresh } = useFetch<{
    session: ExamSession | null;
    allocations: Paginated<Allocation> | null;
    incidents: Paginated<Incident> | null;
  }>(
    async () => {
      if (!id) {
        return { session: null, allocations: null, incidents: null };
      }
      const [session, allocations, incidents] = await Promise.all([
        getExamSession(id).catch(() => null),
        getAllocationForSession(id).catch(() => null),
        getIncidentsForSession(id).catch(() => null),
      ]);
      return { session, allocations, incidents };
    },
    [id],
  );

  const session = data?.session ?? null;
  const allocations = data?.allocations?.results ?? [];
  const incidents = data?.incidents?.results ?? [];

  const fillPct =
    session && session.capacity > 0
      ? (session.registered / session.capacity) * 100
      : 0;
  const actions = session ? availableActions(session.status) : [];

  async function runAction(action: "cancel" | "draft" | "publish" | "reschedule") {
    if (!session) return;
    setActionError(null);
    setPendingAction(action);
    try {
      if (action === "cancel") {
        await cancelExamSession(session.id);
      } else if (action === "draft") {
        await draftExamSession(session.id);
      } else if (action === "publish") {
        await publishExamSession(session.id);
      } else if (action === "reschedule") {
        // Same UX as the parent page: shift the start by 30 minutes.
        // A real app would open a date/time picker here.
        const start = new Date(session.starts_at);
        const end = new Date(session.ends_at);
        const shiftedStart = new Date(start.getTime() + 30 * 60 * 1000);
        const shiftedEnd = new Date(end.getTime() + 30 * 60 * 1000);
        await rescheduleExamSession(session.id, {
          starts_at: shiftedStart.toISOString(),
          ends_at: shiftedEnd.toISOString(),
        });
      }
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <DashboardShell
      title={session ? session.course_code ?? session.course_title ?? "Session" : "Session"}
      subtitle={session ? (session.course_title ?? "Examination session") : "Loading…"}
      actions={
        <Button
          variant="ghost"
          size="md"
          iconLeft="arrow-right"
          onClick={() => router.push("/dashboard/exams")}
        >
          <span className="-mt-px inline-block rotate-180">Back to examinations</span>
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load session">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      {actionError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Action failed">
            {actionError}
          </StatusBanner>
        </div>
      ) : null}

      {/* Header + lifecycle actions */}
      <Card className="mb-6">
        {isLoading && !session ? (
          <p className="text-sm text-ink-500">Loading session…</p>
        ) : session ? (
          <div className="grid gap-5 lg:grid-cols-[1fr_auto]">
            <div>
              <p className="eyebrow text-ink-500">{session.period_code ?? "Cycle"}</p>
              <h2 className="mt-1 text-2xl font-semibold text-ink-900">
                {session.course_code} — {session.course_title ?? "Untitled session"}
              </h2>
              <p className="mt-1 text-sm text-ink-500">
                {session.invigilators_required} invigilator
                {session.invigilators_required === 1 ? "" : "s"} required ·{" "}
                {fmtDuration(session.duration_minutes)} duration
              </p>
              {session.special_requirements ? (
                <p className="mt-3 inline-flex items-center gap-2 rounded-xl bg-amber-50 px-3 py-2 text-xs italic text-amber-800 ring-1 ring-inset ring-amber-200">
                  <Icon name="alert" className="h-3.5 w-3.5" />
                  {session.special_requirements}
                </p>
              ) : null}
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Badge tone={statusTone[session.status].tone} withDot>
                  {statusTone[session.status].label}
                </Badge>
                <div className="flex w-64 items-center gap-3">
                  <span className="text-xs text-ink-500">
                    {session.registered} / {session.capacity} registered
                  </span>
                  <ProgressBar
                    value={fillPct}
                    tone={fillPct > 95 ? "warning" : "brand"}
                    className="flex-1"
                  />
                </div>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              {actions.length > 0 ? (
                actions.map((a) => (
                  <Button
                    key={a.key}
                    variant={a.tone}
                    size="md"
                    onClick={() => void runAction(a.key)}
                    disabled={pendingAction !== null}
                  >
                    {pendingAction === a.key ? "…" : a.label}
                  </Button>
                ))
              ) : (
                <span className="text-xs text-ink-400">
                  No lifecycle actions available
                </span>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-ink-500">Session not found.</p>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          {/* Schedule --------------------------------------------------- */}
          <Card>
            <CardHeader eyebrow="Schedule" title="When and where" />
            <dl className="mt-5 grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                  Date
                </dt>
                <dd className="mt-1 text-sm font-semibold text-ink-900">
                  {session ? fmtDate(session.starts_at) : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                  Time
                </dt>
                <dd className="mt-1 text-sm font-semibold tnum text-ink-900">
                  {session
                    ? `${fmtTime(session.starts_at)} – ${fmtTime(session.ends_at)}`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                  Room
                </dt>
                <dd className="mt-1 inline-flex items-center gap-2 text-sm text-ink-900">
                  <Icon name="map-pin" className="h-3.5 w-3.5 text-ink-400" />
                  {session?.room_code ?? "No room assigned"}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                  Hierarchy
                </dt>
                <dd className="mt-1 text-sm text-ink-700">
                  {session
                    ? `${session.faculty_code ?? "—"} · ${session.department_code ?? "—"} · ${session.program_code ?? "—"}`
                    : "—"}
                </dd>
              </div>
            </dl>
          </Card>

          {/* Assigned invigilators ------------------------------------- */}
          <Card padded={false}>
            <div className="border-b border-ink-100 p-5">
              <CardHeader
                eyebrow="Staffing"
                title="Assigned invigilators"
                subtitle="From the latest allocation run. Re-run the engine to refresh."
              />
            </div>
            {allocations.length === 0 ? (
              <div className="p-8 text-center text-sm text-ink-500">
                {isLoading
                  ? "Loading assignments…"
                  : "No invigilators assigned yet. Run the engine from the Allocations page."}
              </div>
            ) : (
              <ul className="divide-y divide-ink-100">
                {allocations.map((a) => (
                  <li
                    key={a.id}
                    className="flex items-center gap-4 px-5 py-3 transition hover:bg-brand-50/30"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white">
                      {initialsOf(a.invigilator_name)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-ink-900">
                        {a.invigilator_name ?? "—"}
                      </p>
                      <p className="text-xs text-ink-500">
                        {a.invigilator_department ?? "—"} · {a.role}
                      </p>
                    </div>
                    <Badge tone={allocationStatusTone[a.status]} withDot>
                      {a.status === "draft" ? "Pending" : a.status}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* Related incidents ------------------------------------------ */}
        <div className="space-y-6">
          <Card padded={false}>
            <div className="border-b border-ink-100 p-5">
              <CardHeader
                eyebrow="Field"
                title="Related incidents"
                subtitle="Reports logged against this session."
              />
            </div>
            {incidents.length === 0 ? (
              <div className="p-8 text-center text-sm text-ink-500">
                {isLoading
                  ? "Loading incidents…"
                  : "No incidents for this session."}
              </div>
            ) : (
              <ul className="divide-y divide-ink-100">
                {incidents.map((i) => (
                  <li
                    key={i.id}
                    className="flex flex-col gap-2 px-5 py-3 transition hover:bg-brand-50/30"
                  >
                    <div className="flex items-center gap-2">
                      <p className="flex-1 truncate text-sm font-semibold text-ink-900">
                        {i.title}
                      </p>
                      <Badge tone={incidentSeverityTone[i.severity]}>
                        {i.severity}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between text-xs text-ink-500">
                      <span>Reported by {i.reporter_email ?? "Anonymous"}</span>
                      <Badge tone={incidentStatusTone[i.status]} withDot>
                        {i.status}
                      </Badge>
                    </div>
                    <span className="text-[11px] text-ink-400">
                      {fmtDateTime(i.reported_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}

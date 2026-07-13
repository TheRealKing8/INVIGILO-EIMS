/**
 * Examinations module — sessions, cycles, and rooms.
 *
 * Reads `getExamSessions` (paginated) and surfaces:
 *   - The new hierarchy fields (faculty, department, programme, year,
 *     semester) on every session.
 *   - Lifecycle action buttons (Cancel, Reschedule, Draft, Publish)
 *     wired to the backend's /cancel/, /draft/, /publish/, /reschedule/
 *     endpoints. The backend enforces which transitions are legal —
 *     a 409 surfaces a friendly error.
 *
 * The page uses ``DashboardShell`` for layout and the existing
 * ``useFetch`` hook for data; the lifecycle buttons update local state
 * and re-fetch the list so the table stays consistent.
 */
"use client";

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
  getExamSessions,
  getExamPeriods,
  publishExamSession,
  rescheduleExamSession,
  type ExamPeriod,
  type ExamSession,
  type Paginated,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { useRouter } from "next/navigation";

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
function fmtDuration(min: number | null | undefined): string {
  if (min == null) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

/**
 * Returns the lifecycle actions available for a session in its current
 * status. The backend is the source of truth for the transition map;
 * the client mirrors the choices that will actually succeed.
 */
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
      // in_progress, completed, cancelled: no actions.
      return [];
  }
}

export default function ExamsPage() {
  const router = useRouter();
  const [page] = useState(1);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const { data, isLoading, error, refresh } = useFetch<
    { sessions: Paginated<ExamSession>; periods: Paginated<ExamPeriod> }
  >(
    () =>
      Promise.all([
        getExamSessions({ page, page_size: 25, ordering: "starts_at" }),
        getExamPeriods({ is_active: "true", page_size: 1 }),
      ]).then(([sessions, periods]) => ({ sessions, periods })),
    [page],
  );

  const sessions = data?.sessions.results ?? [];
  const total = data?.sessions.count ?? 0;
  const activeCycle = data?.periods.results[0];

  async function runAction(
    session: ExamSession,
    action: "cancel" | "draft" | "publish" | "reschedule",
  ) {
    setActionError(null);
    setPendingId(session.id);
    try {
      if (action === "cancel") {
        await cancelExamSession(session.id);
      } else if (action === "draft") {
        await draftExamSession(session.id);
      } else if (action === "publish") {
        await publishExamSession(session.id);
      } else if (action === "reschedule") {
        // Reschedule shifts the start by 30 minutes. Real apps would
        // open a date/time picker; this is a sensible default for the
        // smoke UX.
        const start = new Date(session.starts_at);
        const end = new Date(session.ends_at);
        const shifted = new Date(start.getTime() + 30 * 60 * 1000);
        const shiftedEnd = new Date(end.getTime() + 30 * 60 * 1000);
        await rescheduleExamSession(session.id, {
          starts_at: shifted.toISOString(),
          ends_at: shiftedEnd.toISOString(),
        });
      }
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <DashboardShell
      title="Examinations"
      subtitle="Cycles · Sessions · Rooms"
      actions={
        <>
          <Button
            variant="ghost"
            size="md"
            iconLeft="refresh"
            onClick={() => void refresh()}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="md"
            iconLeft="plus"
            onClick={() => router.push("/dashboard/exams/new")}
          >
            New exam
          </Button>
        </>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load examinations">
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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Active cycle", value: activeCycle?.name ?? (isLoading ? "…" : "—") },
          { label: "Sessions total", value: total ? String(total) : isLoading ? "…" : "0" },
          { label: "Sessions on this page", value: sessions.length ? String(sessions.length) : "0" },
          { label: "First session", value: sessions[0] ? fmtDate(sessions[0].starts_at) : "—" },
        ].map((s) => (
          <div
            key={s.label}
            className="rounded-3xl bg-surface p-5 ring-1 ring-ink-200 shadow-[var(--shadow-card)]"
          >
            <p className="text-sm text-ink-500">{s.label}</p>
            <p className="mt-2 text-2xl font-semibold tnum text-ink-900">{s.value}</p>
          </div>
        ))}
      </div>

      <Card padded={false} className="mt-6">
        <div className="flex flex-col gap-4 border-b border-ink-100 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardHeader
              eyebrow="Schedule"
              title="Upcoming exams"
              subtitle="All sessions in the current cycle, by start time."
            />
          </div>
        </div>

        {sessions.length === 0 ? (
          <div className="p-10 text-center text-sm text-ink-500">
            {isLoading ? "Loading sessions…" : "No exam sessions yet. Create one to get started."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-ink-100 text-left text-sm">
              <thead className="bg-ink-100/40">
                <tr>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Code</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Title</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Hierarchy</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">When</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Room</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Capacity</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Status</th>
                  <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100 bg-surface">
                {sessions.map((e) => {
                  const fill = e.capacity > 0 ? (e.registered / e.capacity) * 100 : 0;
                  const actions = availableActions(e.status);
                  const isPending = pendingId === e.id;
                  return (
                    <tr
                      key={e.id}
                      className="cursor-pointer transition hover:bg-brand-50/30"
                      onClick={() => router.push(`/dashboard/exams/${e.id}`)}
                    >
                      <td className="px-5 py-4 align-top">
                        <span className="rounded-md bg-ink-100 px-2 py-1 font-mono text-xs font-semibold text-ink-700">
                          {e.course_code ?? "—"}
                        </span>
                      </td>
                      <td className="px-5 py-4 align-top">
                        <p className="text-sm font-semibold text-ink-900">{e.course_title ?? "Untitled session"}</p>
                        <p className="mt-0.5 text-xs text-ink-500">
                          {e.invigilators_required} invigilator{e.invigilators_required === 1 ? "" : "s"} · {fmtDuration(e.duration_minutes)}
                        </p>
                        {e.special_requirements ? (
                          <p className="mt-1 max-w-md text-xs italic text-ink-500" title={e.special_requirements}>
                            ✱ {e.special_requirements}
                          </p>
                        ) : null}
                      </td>
                      <td className="px-5 py-4 align-top">
                        <p className="text-xs text-ink-700">
                          <span className="font-semibold">{e.faculty_code ?? "—"}</span>
                          <span className="text-ink-400"> · </span>
                          {e.department_code ?? "—"}
                        </p>
                        <p className="mt-0.5 text-xs text-ink-500">
                          {e.program_code ?? "—"}
                        </p>
                        {e.course_unit_code ? (
                          <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-800 ring-1 ring-inset ring-brand-100">
                            Y{e.course_unit_year ?? "?"}S{e.course_unit_semester ?? "?"} · {e.course_unit_code}
                          </p>
                        ) : null}
                      </td>
                      <td className="px-5 py-4 align-top">
                        <p className="text-sm font-medium text-ink-900">{fmtDate(e.starts_at)}</p>
                        <p className="text-xs text-ink-500 tnum">{fmtTime(e.starts_at)} – {fmtTime(e.ends_at)}</p>
                      </td>
                      <td className="px-5 py-4 align-top">
                        <span className="inline-flex items-center gap-2 text-sm text-ink-700">
                          <Icon name="map-pin" className="h-3.5 w-3.5 text-ink-400" />
                          {e.room_code ?? "—"}
                        </span>
                      </td>
                      <td className="px-5 py-4 w-48 align-top">
                        <div className="flex items-center justify-between text-xs text-ink-500">
                          <span className="tnum">
                            {e.registered} / {e.capacity}
                          </span>
                          <span className="tnum">{fill.toFixed(0)}%</span>
                        </div>
                        <ProgressBar
                          value={fill}
                          tone={fill > 95 ? "warning" : "brand"}
                          className="mt-1.5"
                        />
                      </td>
                      <td className="px-5 py-4 align-top">
                        <Badge tone={statusTone[e.status].tone} withDot>
                          {statusTone[e.status].label}
                        </Badge>
                      </td>
                      <td className="px-5 py-4 align-top text-right">
                        <div
                          className="flex flex-col items-end gap-1.5"
                          onClick={(ev) => ev.stopPropagation()}
                        >
                          {actions.length > 0 ? (
                            actions.map((a) => (
                              <Button
                                key={a.key}
                                variant={a.tone}
                                size="sm"
                                onClick={() => void runAction(e, a.key)}
                                disabled={isPending}
                              >
                                {isPending ? "…" : a.label}
                              </Button>
                            ))
                          ) : (
                            <span className="text-xs text-ink-400">—</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-ink-100 px-5 py-3 text-xs text-ink-500">
          <span>Showing {sessions.length} of {total}</span>
        </div>
      </Card>
    </DashboardShell>
  );
}

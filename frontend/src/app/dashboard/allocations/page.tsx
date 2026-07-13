/**
 * Allocations module — the engine and its conflicts.
 *
 * Live data from `getAllocations` and `getAllocationRuns`. The
 * "Run engine" button calls `runAllocationEngine` for the active
 * exam period and refreshes the page state.
 */
"use client";

import { useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { Icon, type IconName } from "@/components/ui/icon";
import { ProgressBar } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  getActiveExamPeriod,
  getAllocationRuns,
  getAllocations,
  getConflicts,
  runAllocationEngine,
  type Allocation,
  type AllocationRun,
  type Conflict,
  type ExamPeriod,
  type Paginated,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { useRouter } from "next/navigation";

const statusTone: Record<
  Allocation["status"],
  { tone: "success" | "warning" | "brand" | "danger"; label: string }
> = {
  confirmed: { tone: "success", label: "Confirmed" },
  draft: { tone: "warning", label: "Pending" },
  rejected: { tone: "danger", label: "Rejected" },
};

function initialsOf(name: string | undefined): string {
  if (!name) return "??";
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function describeConflict(c: Conflict): string {
  const a = c.invigilator_name ?? "an invigilator";
  const s = c.session_code ?? "a session";
  switch (c.type) {
    case "double_booking":
      return `${a} is double-booked across ${s}.`;
    case "dept_mix":
      return `Department-mix conflict on ${s}: ${a} is from the same department as another invigilator.`;
    case "no_eligible_invigilators":
      return `No eligible invigilators available for ${s}.`;
    case "no_room_capacity":
      return `No room with sufficient capacity for ${s}.`;
    case "workload_cap":
      return `${a} would exceed their workload cap on ${s}.`;
    case "unavailability":
      return `${a} is marked unavailable for ${s}.`;
  }
}

export default function AllocationsPage() {
  const router = useRouter();
  const [engineState, setEngineState] = useState<"idle" | "running" | "error">("idle");
  const [engineError, setEngineError] = useState<string | null>(null);

  const { data, isLoading, error, refresh } = useFetch<{
    period: ExamPeriod | null;
    allocs: Paginated<Allocation> | null;
    runs: Paginated<AllocationRun> | null;
    conflicts: Paginated<Conflict> | null;
  }>(async () => {
    const period = await getActiveExamPeriod().catch(() => null);
    const [allocs, runs, conflicts] = await Promise.all([
      getAllocations({ page: 1, page_size: 25 }).catch(() => null),
      getAllocationRuns({ page: 1, page_size: 5 }).catch(() => null),
      getConflicts({ page: 1, page_size: 5 }).catch(() => null),
    ]);
    return { period, allocs, runs, conflicts };
  }, []);

  const allocs = data?.allocs?.results ?? [];
  const latestRun: AllocationRun | undefined = data?.runs?.results[0];
  const conflicts = data?.conflicts?.results ?? [];
  const coverage = latestRun ? Math.round(parseFloat(latestRun.capacity_utilisation) * 100) : 0;

  async function handleRun() {
    if (!data?.period) {
      setEngineError("No active exam period. Activate one from the Exams page before running the engine.");
      setEngineState("error");
      return;
    }
    setEngineState("running");
    setEngineError(null);
    try {
      await runAllocationEngine(data.period.id);
      await refresh();
      setEngineState("idle");
    } catch (err) {
      setEngineError(err instanceof Error ? err.message : String(err));
      setEngineState("error");
    }
  }

  return (
    <DashboardShell
      title="Allocations"
      subtitle="Smart engine · Conflict checks"
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
            iconLeft="lightning"
            disabled={engineState === "running"}
            onClick={handleRun}
          >
            {engineState === "running" ? "Running…" : "Run engine"}
          </Button>
        </>
      }
    >
      {error || engineError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Engine error">
            {engineError ?? error?.message}
          </StatusBanner>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.5fr_0.5fr]">
        <Card padded={false}>
          <div className="flex items-center justify-between border-b border-ink-100 p-5">
            <CardHeader
              eyebrow={data?.period ? data.period.code : "Active cycle"}
              title="Allocation overview"
              subtitle="Invigilator-to-session mapping for the current cycle."
            />
            <div className="flex items-center gap-2">
              <Badge tone="success" withDot>
                {latestRun ? `Coverage ${coverage}%` : "No runs yet"}
              </Badge>
              <Badge tone={conflicts.length > 0 ? "warning" : "neutral"} withDot>
                {conflicts.length} conflict{conflicts.length === 1 ? "" : "s"}
              </Badge>
            </div>
          </div>

          {allocs.length === 0 ? (
            <div className="p-10 text-center text-sm text-ink-500">
              {isLoading
                ? "Loading allocations…"
                : "No allocations yet. Click “Run engine” to generate them."}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-ink-100 text-left text-sm">
                <thead className="bg-ink-100/40">
                  <tr>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Exam</th>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Invigilator</th>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Room</th>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Role</th>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100 bg-surface">
                  {allocs.map((r) => (
                    <tr key={r.id} className="transition hover:bg-brand-50/30">
                      <td className="px-5 py-4">
                        <p className="text-sm font-semibold text-ink-900">
                          {r.exam_code ?? "—"}
                        </p>
                        <p className="text-xs text-ink-500">
                          {r.exam_title ?? ""}
                        </p>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-700 text-[11px] font-semibold text-white">
                            {initialsOf(r.invigilator_name)}
                          </span>
                          <span className="text-sm text-ink-700">
                            {r.invigilator_name ?? "—"}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <span className="inline-flex items-center gap-2 text-sm text-ink-700">
                          <Icon name="map-pin" className="h-3.5 w-3.5 text-ink-400" />
                          {r.room_code ?? "—"}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <span className="text-sm capitalize text-ink-700">
                          {r.role}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <Badge tone={statusTone[r.status].tone} withDot>
                          {statusTone[r.status].label}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="space-y-6">
          <CardDark>
            <p className="eyebrow text-brand-300">Conflict detection</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">
              {conflicts.length === 0
                ? "No conflicts"
                : `${conflicts.length} conflict${conflicts.length === 1 ? "" : "s"} to review`}
            </h3>
            <p className="mt-2 text-sm text-brand-100/80">
              {conflicts.length === 0
                ? "The latest run placed every session cleanly. Run the engine again to re-validate."
                : "Review each conflict and either re-run the engine or reassign invigilators manually."}
            </p>
            {latestRun ? (
              <Button
                variant="light"
                size="sm"
                iconRight="arrow-right"
                className="mt-4"
                onClick={() => router.push(`/dashboard/allocations/${latestRun.id}`)}
              >
                View run details
              </Button>
            ) : null}
            {conflicts.length > 0 ? (
              <div className="mt-5 space-y-3">
                {conflicts.slice(0, 3).map((c) => (
                  <div
                    key={c.id}
                    className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4"
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-amber-400/20 text-amber-200 ring-1 ring-inset ring-amber-400/30">
                        <Icon name="alert" className="h-4 w-4" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-semibold text-white">
                          {c.session_code ?? "Session"} · {c.type.replace(/_/g, " ")}
                        </p>
                        <p className="mt-1 text-xs text-brand-100/70">
                          {describeConflict(c)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </CardDark>

          <Card>
            <CardHeader eyebrow="Engine" title="How the run went" />
            <ol className="mt-5 space-y-3 text-sm">
              {[
                {
                  label: "Sessions placed",
                  value: latestRun
                    ? `${latestRun.sessions_placed} / ${latestRun.sessions_total}`
                    : "—",
                },
                { label: "Avg. inv. workload", value: latestRun ? latestRun.avg_workload : "—" },
                { label: "Max inv. workload", value: latestRun ? String(latestRun.max_workload) : "—" },
                {
                  label: "Capacity utilisation",
                  value: latestRun ? `${coverage}%` : "—",
                },
                {
                  label: "Time to run",
                  value: latestRun ? `${latestRun.runtime_seconds}s` : "—",
                },
              ].map((it) => (
                <li
                  key={it.label}
                  className="flex items-center justify-between border-b border-ink-100 pb-2 last:border-b-0 last:pb-0"
                >
                  <span className="text-ink-500">{it.label}</span>
                  <span className="tnum font-semibold text-ink-900">{it.value}</span>
                </li>
              ))}
            </ol>
            {latestRun ? (
              <div className="mt-4">
                <ProgressBar value={coverage} tone={coverage >= 95 ? "success" : "warning"} />
              </div>
            ) : null}
          </Card>

          <Card>
            <CardHeader eyebrow="Rules" title="What the engine checks" />
            <ul className="mt-4 space-y-2.5 text-sm text-ink-700">
              {(
                [
                  { icon: "shield" as IconName, label: "No double-booking — one invigilator, one session at a time." },
                  { icon: "users" as IconName, label: "Department mixing — no two invigilators in a session share a department." },
                  { icon: "calendar" as IconName, label: "Availability — invigilators marked unavailable for the date are skipped." },
                  { icon: "map-pin" as IconName, label: "Room capacity — sessions whose head-count exceeds the room are pre-flighted out." },
                  { icon: "gauge" as IconName, label: "Workload cap — never exceed an invigilator's per-cycle maximum." },
                  { icon: "lightning" as IconName, label: "Most-constrained first — heavy / under-resourced sessions get prioritised." },
                ]
              ).map((it) => (
                <li key={it.label} className="flex items-start gap-2.5">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100">
                    <Icon name={it.icon} className="h-3 w-3" />
                  </span>
                  <span className="leading-relaxed">{it.label}</span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-[11px] uppercase tracking-[0.14em] text-ink-400">
              Rule-based · deterministic · AI will optimise the output in a later phase.
            </p>
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}

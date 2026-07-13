/**
 * Allocation run detail — drill-in from the /dashboard/allocations
 * "View run details" link.
 *
 * The run is a snapshot: read-only. The page shows the run's
 * headline stats, the per-session outcomes (grouped allocations),
 * and the full conflict list. Re-running the engine is an action
 * on the parent allocations page, so this page links back there.
 */
"use client";

import { useParams, useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { Icon, type IconName } from "@/components/ui/icon";
import { ProgressBar } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  getAllocationRun,
  getAllocationsForRun,
  getConflicts,
  type Allocation,
  type AllocationRun,
  type Conflict,
  type Paginated,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

const allocationStatusTone: Record<
  Allocation["status"],
  "success" | "warning" | "danger"
> = {
  confirmed: "success",
  draft: "warning",
  rejected: "danger",
};

const conflictTone: Record<Conflict["severity"], "warning" | "danger"> = {
  warning: "warning",
  error: "danger",
};

function initialsOf(name: string | undefined): string {
  if (!name) return "??";
  return name
    .split(/\s+/)
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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

export default function AllocationRunDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const { data, isLoading, error } = useFetch<{
    run: AllocationRun | null;
    allocations: Paginated<Allocation> | null;
    conflicts: Paginated<Conflict> | null;
  }>(
    async () => {
      if (!id) {
        return { run: null, allocations: null, conflicts: null };
      }
      const [run, allocations, conflicts] = await Promise.all([
        getAllocationRun(id).catch(() => null),
        getAllocationsForRun(id).catch(() => null),
        getConflicts({ run: id, page_size: 100 }).catch(() => null),
      ]);
      return { run, allocations, conflicts };
    },
    [id],
  );

  const run = data?.run ?? null;
  const allocations = data?.allocations?.results ?? [];
  const conflicts = data?.conflicts?.results ?? [];

  const coverage = run
    ? Math.round(parseFloat(run.capacity_utilisation) * 100)
    : 0;

  // Group allocations by session for the per-session outcomes card.
  const bySession: Record<
    string,
    { sessionCode: string | null; rows: Allocation[] }
  > = allocations.reduce(
    (acc, a) => {
      const key = a.session;
      if (!acc[key]) {
        acc[key] = { sessionCode: a.exam_code ?? null, rows: [] };
      }
      acc[key].rows.push(a);
      return acc;
    },
    {} as Record<string, { sessionCode: string | null; rows: Allocation[] }>,
  );
  const sessionGroups = Object.values(bySession);

  return (
    <DashboardShell
      title={run ? `Run · ${run.period_code ?? run.period}` : "Allocation run"}
      subtitle={
        run
          ? `Triggered ${fmtTime(run.created_at)}`
          : "Loading run…"
      }
      actions={
        <Button
          variant="ghost"
          size="md"
          iconLeft="arrow-right"
          onClick={() => router.push("/dashboard/allocations")}
        >
          <span className="-mt-px inline-block rotate-180">Back to allocations</span>
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load run">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      {/* Header card — headline stats + back-to-engine link */}
      <div className="mb-6 grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <Card>
          <p className="eyebrow text-ink-500">Snapshot</p>
          <h2 className="mt-1 text-2xl font-semibold text-ink-900">
            {run ? `${run.sessions_placed} / ${run.sessions_total} sessions placed` : "Loading…"}
          </h2>
          <p className="mt-1 text-sm text-ink-500">
            {run
              ? `Runtime ${run.runtime_seconds}s · Coverage ${coverage}% · Avg workload ${run.avg_workload} (max ${run.max_workload})`
              : "Awaiting data."}
          </p>
          {run ? (
            <div className="mt-4">
              <ProgressBar
                value={coverage}
                tone={coverage >= 95 ? "success" : "warning"}
              />
            </div>
          ) : null}
          <dl className="mt-5 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Period
              </dt>
              <dd className="mt-1 font-semibold text-ink-900">
                {run?.period_code ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Triggered by
              </dt>
              <dd className="mt-1 truncate font-semibold text-ink-900">
                {run?.triggered_by_email ?? "system"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Started
              </dt>
              <dd className="mt-1 tnum text-ink-900">{fmtTime(run?.created_at)}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Finished
              </dt>
              <dd className="mt-1 tnum text-ink-900">{fmtTime(run?.finished_at)}</dd>
            </div>
          </dl>
        </Card>

        <CardDark>
          <p className="eyebrow text-brand-300">Re-run the engine</p>
          <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">
            {conflicts.length === 0
              ? "Everything placed cleanly"
              : `${conflicts.length} conflict${conflicts.length === 1 ? "" : "s"} to review`}
          </h3>
          <p className="mt-2 text-sm text-brand-100/80">
            The engine run is a snapshot. To re-validate, head back to the
            allocations page and trigger a fresh run.
          </p>
          <Button
            variant="light"
            size="md"
            iconRight="lightning"
            fullWidth
            className="mt-5"
            onClick={() => router.push("/dashboard/allocations")}
          >
            Open allocations
          </Button>
        </CardDark>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        {/* Per-session outcomes ------------------------------------- */}
        <Card padded={false}>
          <div className="border-b border-ink-100 p-5">
            <CardHeader
              eyebrow="Outcomes"
              title="Per-session allocations"
              subtitle="One block per session this run placed."
            />
          </div>
          {isLoading ? (
            <div className="p-8 text-center text-sm text-ink-500">
              Loading outcomes…
            </div>
          ) : sessionGroups.length === 0 ? (
            <div className="p-8 text-center text-sm text-ink-500">
              {run
                ? "This run placed no sessions. Conflicts below explain why."
                : "No data yet."}
            </div>
          ) : (
            <ul className="divide-y divide-ink-100">
              {sessionGroups.map((g) => (
                <li key={g.rows[0].session} className="px-5 py-4">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-sm font-semibold text-ink-900">
                      {g.sessionCode ?? g.rows[0].exam_title ?? "Session"}
                    </p>
                    <Badge tone="brand">
                      {g.rows.length} invigilator
                      {g.rows.length === 1 ? "" : "s"}
                    </Badge>
                  </div>
                  <ol className="space-y-1.5">
                    {g.rows.map((a) => (
                      <li
                        key={a.id}
                        className="flex items-center gap-3 rounded-xl bg-ink-100/40 px-3 py-2"
                      >
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-[11px] font-semibold text-white">
                          {initialsOf(a.invigilator_name)}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm text-ink-900">
                            {a.invigilator_name ?? "—"}
                          </p>
                          <p className="text-[11px] text-ink-500">
                            {a.invigilator_department ?? "—"} · {a.role}
                          </p>
                        </div>
                        <Badge tone={allocationStatusTone[a.status]} withDot>
                          {a.status === "draft" ? "Pending" : a.status}
                        </Badge>
                      </li>
                    ))}
                  </ol>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Conflicts + engine recap -------------------------------- */}
        <div className="space-y-6">
          <Card padded={false}>
            <div className="border-b border-ink-100 p-5">
              <CardHeader
                eyebrow="Conflicts"
                title={`${conflicts.length} recorded`}
                subtitle="Each row is a reason the engine skipped or back-filled an invigilator."
              />
            </div>
            {conflicts.length === 0 ? (
              <div className="p-8 text-center text-sm text-ink-500">
                Run placed every session cleanly.
              </div>
            ) : (
              <ul className="divide-y divide-ink-100">
                {conflicts.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-start gap-3 px-5 py-3 transition hover:bg-brand-50/30"
                  >
                    <span
                      className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset ${
                        c.severity === "error"
                          ? "bg-rose-50 text-rose-700 ring-rose-200"
                          : "bg-amber-50 text-amber-700 ring-amber-200"
                      }`}
                    >
                      <Icon name="alert" className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-semibold text-ink-900">
                          {c.session_code ?? "Session"}
                        </p>
                        <Badge tone={conflictTone[c.severity]}>
                          {c.type.replace(/_/g, " ")}
                        </Badge>
                      </div>
                      <p className="mt-0.5 text-xs text-ink-500">
                        {describeConflict(c)}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
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
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}

/**
 * Dashboard home — the operations overview.
 *
 * Pulls live data from the backend via useFetch; falls back to a clean
 * empty state when the API has no data yet.
 */
"use client";

import { useMemo } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { HeroStat, Stat, StatGrid } from "@/components/ui/stat";
import { Icon } from "@/components/ui/icon";
import { ProgressBar, Sparkline } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import { getDashboardSummary, type DashboardSummary, type ExamSession, type Incident } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

const greetingByHour = (h: number) => {
  if (h < 5) return "Still up?";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 22) return "Good evening";
  return "Late night";
};

const sessionStatusTone: Record<ExamSession["status"], { tone: "brand" | "success" | "warning" | "neutral" | "danger"; label: string }> = {
  draft: { tone: "neutral", label: "Draft" },
  scheduled: { tone: "brand", label: "Scheduled" },
  ready: { tone: "success", label: "Ready" },
  in_progress: { tone: "warning", label: "In progress" },
  pending: { tone: "warning", label: "Pending" },
  completed: { tone: "neutral", label: "Completed" },
  cancelled: { tone: "danger", label: "Cancelled" },
};

function timeOf(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function dateOf(iso: string): string {
  return new Date(iso).toLocaleDateString([], { month: "short", day: "2-digit" });
}

function activityFor(incident: Incident) {
  return {
    who: incident.reporter_email ?? "Anonymous",
    what: incident.title,
    when: dateOf(incident.reported_at),
    tone:
      incident.severity === "critical" || incident.severity === "high"
        ? ("danger" as const)
        : incident.severity === "medium"
        ? ("warning" as const)
        : ("info" as const),
  };
}

export default function DashboardPage() {
  const hour = new Date().getHours();
  const greeting = greetingByHour(hour);

  const { data, isLoading, error, refresh } = useFetch<DashboardSummary>(
    () => getDashboardSummary(),
    [],
  );

  const sessions = data?.upcoming_sessions ?? [];
  const incidents = data?.recent_incidents ?? [];
  const runs = data?.recent_runs ?? [];

  const activePeriodLabel = useMemo(() => {
    if (!data?.active_period) return "—";
    return `${data.active_period.name} (${data.active_period.code})`;
  }, [data?.active_period]);

  const latestRun = runs[0];

  return (
    <DashboardShell
      title={`${greeting}, Operations`}
      subtitle="Live control room"
      actions={
        <Button variant="ghost" size="sm" iconLeft="refresh" onClick={() => void refresh()}>
          Refresh
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load dashboard">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      {/* Status strip ------------------------------------------------- */}
      <Card className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100">
            <span className="h-2 w-2 rounded-full bg-brand-500 pulse-ring" />
          </span>
          <p className="text-sm text-ink-700">
            <span className="font-semibold text-ink-900">All systems operational.</span>
            <span className="ml-2 text-ink-500">
              {data
                ? `${data.total_sessions} sessions · ${data.total_invigilators} invigilators · ${data.total_incidents_open} open incidents`
                : isLoading
                ? "Loading…"
                : "No data yet"}
            </span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand" withDot>Live</Badge>
          {latestRun ? (
            <Badge tone="success" withDot>
              Coverage {Math.round(parseFloat(latestRun.capacity_utilisation) * 100)}%
            </Badge>
          ) : null}
          <Badge tone={data && data.total_incidents_open > 0 ? "warning" : "neutral"} withDot>
            {data ? `${data.total_incidents_open} alerts` : "— alerts"}
          </Badge>
        </div>
      </Card>

      {/* KPI tiles ----------------------------------------------------- */}
      <StatGrid>
        <Stat
          icon="calendar"
          label="Active period"
          value={data?.active_period?.name ?? (isLoading ? "…" : "—")}
          hint={data?.active_period ? data.active_period.code : "No active period"}
        />
        <Stat
          icon="users"
          label="Total invigilators"
          value={data ? String(data.total_invigilators) : isLoading ? "…" : "—"}
          hint="registered profiles"
        />
        <Stat
          icon="check"
          label="Sessions scheduled"
          value={data ? String(data.total_sessions) : isLoading ? "…" : "—"}
          hint="across all periods"
        />
        <Stat
          icon="alert"
          label="Open incidents"
          value={data ? String(data.total_incidents_open) : isLoading ? "…" : "—"}
          hint="awaiting acknowledgement"
        />
      </StatGrid>

      {/* Schedule + Workload panel ------------------------------------- */}
      <div className="mt-8 grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <Card padded={false}>
          <div className="p-6">
            <CardHeader
              eyebrow="Upcoming"
              title="Examination schedule"
              subtitle="Live view of sessions, staffing, and readiness."
              actions={
                <Button variant="primary" size="sm" iconLeft="plus">
                  New session
                </Button>
              }
            />

            {sessions.length === 0 ? (
              <div className="mt-6 rounded-2xl border border-dashed border-ink-200 bg-ink-50/40 p-8 text-center text-sm text-ink-500">
                {isLoading
                  ? "Loading sessions…"
                  : "No upcoming exam sessions yet. Create one to get started."}
              </div>
            ) : (
              <div className="mt-6 overflow-hidden rounded-2xl ring-1 ring-ink-200">
                <table className="min-w-full divide-y divide-ink-100 text-left text-sm">
                  <thead className="bg-ink-100/60">
                    <tr>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Date · Time</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Exam</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Room</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Candidates</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100 bg-surface">
                    {sessions.map((s) => (
                      <tr key={s.id} className="transition hover:bg-brand-50/40">
                        <td className="px-4 py-3 text-sm font-semibold tnum text-ink-900">
                          {dateOf(s.starts_at)} · {timeOf(s.starts_at)}
                        </td>
                        <td className="px-4 py-3">
                          <p className="text-sm font-medium text-ink-900">
                            {s.course_code} — {s.course_title}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-sm text-ink-700">
                          <span className="inline-flex items-center gap-2">
                            <Icon name="map-pin" className="h-3.5 w-3.5 text-ink-400" />
                            {s.room_code ?? "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm tnum text-ink-700">
                          {s.registered} / {s.capacity}
                        </td>
                        <td className="px-4 py-3">
                          <Badge tone={sessionStatusTone[s.status].tone} withDot>
                            {sessionStatusTone[s.status].label}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Card>

        <div className="space-y-6">
          <CardDark>
            <p className="eyebrow text-brand-300">Latest allocation run</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">
              {latestRun ? `${latestRun.sessions_placed} / ${latestRun.sessions_total}` : "No runs yet"}
            </h3>
            <p className="mt-2 text-sm text-brand-100/80">
              {latestRun
                ? `Placed ${latestRun.sessions_placed} of ${latestRun.sessions_total} sessions in ${latestRun.runtime_seconds}s.`
                : "Run the engine to assign invigilators."}
            </p>
            <div className="mt-5">
              <ProgressBar
                value={latestRun ? Math.round(parseFloat(latestRun.capacity_utilisation) * 100) : 0}
                tone="success"
              />
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-brand-200/70">
              <span>0%</span>
              <span>Capacity utilisation</span>
              <span>100%</span>
            </div>
            <div className="mt-5 grid grid-cols-3 gap-3">
              <HeroStat label="Avg load" value={latestRun ? latestRun.avg_workload : "—"} sub="per invigilator" />
              <HeroStat label="Max load" value={latestRun ? String(latestRun.max_workload) : "—"} sub="this cycle" />
              <HeroStat
                label="Period"
                value={latestRun?.period_code ?? "—"}
                sub="active"
              />
            </div>
          </CardDark>

          <Card>
            <CardHeader
              eyebrow="Right now"
              title="Invigilator on duty"
              subtitle="Today's session attendance over time"
            />
            <div className="mt-5">
              <Sparkline
                values={[42, 51, 48, 60, 71, 78, 84, 90, 88, 92, 95, 97, 99, 100, 96, 92]}
                tone="success"
                width={300}
                height={64}
              />
            </div>
            <div className="mt-3 flex items-center justify-between text-[11px] text-ink-500">
              <span>07:00</span>
              <span>12:00</span>
              <span>17:00</span>
            </div>
          </Card>
        </div>
      </div>

      {/* Activity + Active period ------------------------------------- */}
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card padded={false}>
          <div className="p-6">
            <CardHeader
              eyebrow="Recent"
              title="Incidents"
              subtitle="Latest reports from the field."
              actions={<Button variant="ghost" size="sm" iconRight="arrow-right">View all</Button>}
            />
            {incidents.length === 0 ? (
              <p className="mt-6 text-sm text-ink-500">
                {isLoading ? "Loading…" : "No recent incidents."}
              </p>
            ) : (
              <ol className="mt-6 space-y-4">
                {incidents.map((i) => {
                  const a = activityFor(i);
                  return (
                    <li key={i.id} className="flex items-start gap-3">
                      <span className="mt-1 flex h-2 w-2 shrink-0 rounded-full bg-brand-500" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-ink-900">
                          <span className="font-semibold">{a.who}</span>{" "}
                          <span className="text-ink-700">{a.what}</span>
                        </p>
                        <p className="mt-0.5 text-xs text-ink-500">
                          {i.severity} · {i.status} · {a.when}
                        </p>
                      </div>
                      <Badge tone={a.tone}>{a.tone}</Badge>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            eyebrow="Active period"
            title={data?.active_period?.name ?? "No active period"}
            subtitle={
              data?.active_period
                ? `${data.active_period.starts_on} → ${data.active_period.ends_on}`
                : "Activate a period from the Exams page to begin."
            }
          />
          <div className="mt-5 space-y-3 text-sm text-ink-700">
            <p>
              <span className="font-semibold text-ink-900">{data?.total_sessions ?? 0}</span> sessions
              scheduled across the cycle.
            </p>
            <p>
              <span className="font-semibold text-ink-900">{data?.total_invigilators ?? 0}</span> invigilators
              registered.
            </p>
            <p>
              <span className="font-semibold text-ink-900">{data?.total_incidents_open ?? 0}</span> incidents
              awaiting acknowledgement.
            </p>
          </div>
        </Card>
      </div>

      {/* Status banner ------------------------------------------------ */}
      {data?.active_period ? (
        <div className="mt-8">
          <StatusBanner tone="info" title="Heads up">
            The {data.active_period.name} cycle is active. Head to the Reports tab to
            generate a fresh attendance summary.
          </StatusBanner>
        </div>
      ) : null}
    </DashboardShell>
  );
}

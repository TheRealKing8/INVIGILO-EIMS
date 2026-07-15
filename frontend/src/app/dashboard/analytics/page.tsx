/**
 * Analytics — the operations control-room view (Phase 16).
 *
 * Single source of truth for "where are we, right now?". Reads the
 * one-shot aggregator endpoint at `/api/v1/analytics/summary/` (see
 * `backend/apps/analytics/views.py`) and renders the same shape in
 * a control-room layout:
 *
 *   * Top row: 4 KPI tiles — coverage, upcoming sessions, check-ins
 *     today, open incidents.
 *   * Middle: workload bars (top 5 invigilators by allocation count)
 *     + the 12-week attendance sparkline.
 *   * Bottom: sessions-by-day for the next 7 days + incidents-by-severity
 *     chips.
 *
 * For INVIGILATOR users the workload list narrows to *their own*
 * allocations (the backend scopes the slice — see
 * `apps/analytics/services.py`). The headline KPIs and the trend
 * remain org-wide, since the invigilator should still see context
 * ("is the cycle on track?") alongside their own data.
 */
"use client";

import { useMemo } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Stat, StatGrid } from "@/components/ui/stat";
import { ProgressBar, Sparkline } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  getAnalyticsSummary,
  type AnalyticsIncidentsBySeverity,
  type AnalyticsSummary,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/use-fetch";

const severityTone: Record<keyof AnalyticsIncidentsBySeverity, Tone> = {
  low: "neutral",
  medium: "warning",
  high: "danger",
  critical: "info",
};

function fmtDay(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function coverageTone(value: number | null): "success" | "warning" | "brand" {
  if (value == null) return "brand";
  if (value >= 90) return "success";
  if (value >= 70) return "warning";
  return "brand";
}

export default function AnalyticsPage() {
  const { user } = useAuth();

  const { data, isLoading, error, refresh } = useFetch<AnalyticsSummary | null>(
    () => getAnalyticsSummary().catch(() => null),
    [],
  );

  // INVIGILATOR gets a self-scoping headline on the workload card;
  // everyone else sees the org-wide pool. The backend has already
  // narrowed the list — this branch is purely cosmetic.
  const isInvigilator = user?.primary_role === "INVIGILATOR";
  const workloadCardTitle = isInvigilator ? "Your workload" : "Top invigilator workload";
  const workloadCardHint = isInvigilator
    ? "Allocations in the current period — you"
    : "Top 5 by allocation count in the current period";

  // Sparkline values from the 12-week attendance trend.
  const trendValues = useMemo(
    () => (data?.attendance_trend ?? []).map((b) => b.count),
    [data?.attendance_trend],
  );

  return (
    <DashboardShell
      title="Analytics"
      subtitle="Control-room KPIs, trends, workload"
      actions={
        <Button
          variant="ghost"
          size="md"
          iconLeft="refresh"
          onClick={() => void refresh()}
        >
          Refresh
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Analytics error">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      {/* Headline KPIs ------------------------------------------------- */}
      <StatGrid>
        <Stat
          icon="gauge"
          label="Allocation coverage"
          value={
            data?.coverage == null
              ? isLoading
                ? "…"
                : "—"
              : `${data.coverage.toFixed(0)}%`
          }
          hint={
            data?.period_code
              ? `Period ${data.period_code} — latest run`
              : "No active examination period"
          }
        />
        <Stat
          icon="calendar"
          label="Upcoming sessions"
          value={
            data
              ? String(data.upcoming_sessions_count)
              : isLoading
                ? "…"
                : "0"
          }
          hint="Next 7 days"
        />
        <Stat
          icon="check"
          label="Check-ins today"
          value={
            data
              ? String(data.checkins_today)
              : isLoading
                ? "…"
                : "0"
          }
          hint={
            data && data.late_count_today > 0
              ? `${data.late_count_today} late`
              : "On-time across the day"
          }
        />
        <Stat
          icon="alert"
          label="Open incidents"
          value={
            data
              ? String(data.open_incidents_count)
              : isLoading
                ? "…"
                : "0"
          }
          hint="Awaiting resolution"
        />
      </StatGrid>

      {/* Workload + attendance trend --------------------------------- */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card padded={false}>
          <div className="border-b border-ink-100 p-5">
            <CardHeader
              eyebrow="Field"
              title={workloadCardTitle}
              subtitle={workloadCardHint}
            />
          </div>
          {!data ? (
            <div className="p-10 text-center text-sm text-ink-500">
              {isLoading ? "Loading workload…" : "No data yet."}
            </div>
          ) : data.invigilator_workload.length === 0 ? (
            <div className="p-10 text-center text-sm text-ink-500">
              {isInvigilator
                ? "You have no allocations in the current period yet."
                : "No allocations in the current period yet."}
            </div>
          ) : (
            <ul className="divide-y divide-ink-100">
              {data.invigilator_workload.map((row) => (
                <li
                  key={row.email}
                  className="flex items-center gap-4 px-5 py-4"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="truncate text-sm font-semibold text-ink-900">
                        {row.name}
                      </p>
                      <p className="shrink-0 text-xs text-ink-500">
                        {row.allocated} / {row.max_per_cycle} sessions
                      </p>
                    </div>
                    <p className="mt-0.5 text-xs text-ink-500">{row.email}</p>
                    <div className="mt-2 flex items-center gap-3">
                      <ProgressBar
                        value={row.fill_pct}
                        tone={coverageTone(row.fill_pct)}
                        className="flex-1"
                      />
                      <span className="w-12 text-right text-xs font-semibold tnum text-ink-700">
                        {row.fill_pct.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <CardDark>
          <p className="eyebrow text-brand-300">Trend</p>
          <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">
            Attendance, last 12 weeks
          </h3>
          <p className="mt-1 text-sm text-brand-100/80">
            Weekly check-in count across all sessions. Use it to spot
            a flattening curve before the cycle peaks.
          </p>
          <div className="mt-5">
            <Sparkline
              values={trendValues.length > 0 ? trendValues : [0]}
              tone="success"
              width={360}
              height={72}
            />
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3 text-brand-100/80">
            <div className="rounded-2xl bg-white/[0.04] p-3 ring-1 ring-inset ring-white/10">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-brand-200/80">
                This week
              </p>
              <p className="mt-1 text-2xl font-semibold tnum text-white">
                {data?.attendance_trend?.at(-1)?.count ?? 0}
              </p>
            </div>
            <div className="rounded-2xl bg-white/[0.04] p-3 ring-1 ring-inset ring-white/10">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-brand-200/80">
                Last week
              </p>
              <p className="mt-1 text-2xl font-semibold tnum text-white">
                {data?.attendance_trend?.at(-2)?.count ?? 0}
              </p>
            </div>
            <div className="rounded-2xl bg-white/[0.04] p-3 ring-1 ring-inset ring-white/10">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-brand-200/80">
                12-wk total
              </p>
              <p className="mt-1 text-2xl font-semibold tnum text-white">
                {data?.attendance_trend?.reduce((s, b) => s + b.count, 0) ?? 0}
              </p>
            </div>
          </div>
        </CardDark>
      </div>

      {/* Sessions by day + incidents by severity -------------------- */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <Card padded={false}>
          <div className="border-b border-ink-100 p-5">
            <CardHeader
              eyebrow="Forecast"
              title="Sessions in the next 7 days"
              subtitle="Grouped by day. Each chip is a course code."
            />
          </div>
          {!data ? (
            <div className="p-10 text-center text-sm text-ink-500">
              {isLoading ? "Loading schedule…" : "No data yet."}
            </div>
          ) : data.sessions_by_day.length === 0 ? (
            <div className="p-10 text-center text-sm text-ink-500">
              No sessions scheduled in the next 7 days.
            </div>
          ) : (
            <ul className="divide-y divide-ink-100">
              {data.sessions_by_day.map((d) => (
                <li
                  key={d.date}
                  className="flex items-center gap-4 px-5 py-3"
                >
                  <div className="w-32 shrink-0">
                    <p className="text-sm font-semibold text-ink-900">
                      {fmtDay(d.date)}
                    </p>
                    <p className="text-[11px] text-ink-500">
                      {d.count} session{d.count === 1 ? "" : "s"}
                    </p>
                  </div>
                  <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
                    {d.courses.length === 0 ? (
                      <span className="text-xs text-ink-400">—</span>
                    ) : (
                      d.courses.map((c) => (
                        <span
                          key={c}
                          className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-semibold text-brand-700 ring-1 ring-inset ring-brand-100"
                        >
                          {c}
                        </span>
                      ))
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader
              eyebrow="Field"
              title="Incidents by severity"
              subtitle="Active period only."
            />
            {!data ? (
              <div className="mt-5 text-sm text-ink-500">
                {isLoading ? "Loading…" : "No data yet."}
              </div>
            ) : (
              <ul className="mt-5 space-y-2">
                {(Object.keys(severityTone) as (keyof AnalyticsIncidentsBySeverity)[]).map(
                  (key) => {
                    const count = data.incidents_by_severity[key];
                    return (
                      <li
                        key={key}
                        className="flex items-center justify-between gap-3 rounded-2xl bg-ink-50/60 px-3 py-2 ring-1 ring-inset ring-ink-100"
                      >
                        <Badge tone={severityTone[key]} withDot>
                          {key}
                        </Badge>
                        <span className="text-sm font-semibold tnum text-ink-900">
                          {count}
                        </span>
                      </li>
                    );
                  },
                )}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader
              eyebrow="Note"
              title="What this view is"
            />
            <p className="mt-3 text-sm text-ink-700">
              One round-trip to the analytics aggregator. Refresh the
              page to re-pull; no per-component polling.
            </p>
            {data?.generated_at ? (
              <p className="mt-2 text-[11px] text-ink-500">
                Generated {fmtTime(data.generated_at)}
              </p>
            ) : null}
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}

/**
 * Audit log — every consequential change in the system is captured
 * by `apps.audit.signals` and surfaced here. Read-only: the audit
 * rows are immutable, so this page has no mutations of its own.
 *
 * Backend: `AuditLogViewSet` (`/api/v1/audit/`).
 *   - `?target_type=`, `?action=`, `?actor=` exact filters
 *   - `?search=` matches target_id or action
 *   - `?ordering=` defaults to `-created_at`
 *
 * Layout:
 *   - 4 KPI tiles (events, actors, targets, last event at)
 *   - Filter row (target type, action, from/to date)
 *   - List with per-row "Show diff" disclosure
 */
"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { Icon, type IconName } from "@/components/ui/icon";
import { Stat, StatGrid } from "@/components/ui/stat";
import { StatusBanner } from "@/components/ui/status-banner";
import { getAuditLogs, type AuditLog } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

// Target types the system actually emits. The "All" entry is the
// default (no filter). These match `apps.<app>.models.<Model.__name__>`
// model labels as the audit middleware writes them.
const TARGET_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All target types" },
  { value: "ExamSession", label: "Exam sessions" },
  { value: "ExamPeriod", label: "Exam periods" },
  { value: "Allocation", label: "Allocations" },
  { value: "AllocationRun", label: "Allocation runs" },
  { value: "Incident", label: "Incidents" },
  { value: "InvigilatorProfile", label: "Invigilator profiles" },
  { value: "User", label: "Users" },
];

/**
 * Map an action verb to a chip tone. We only colour the verbs we see
 * most often — anything unknown falls back to "neutral".
 */
function actionTone(action: string): "success" | "warning" | "danger" | "brand" | "neutral" {
  if (action.startsWith("create") || action === "login" || action === "register") return "success";
  if (action === "delete" || action === "hard_delete") return "danger";
  if (action === "cancel" || action === "escalate" || action === "reject") return "warning";
  if (
    action.startsWith("update") ||
    action === "publish" ||
    action === "reschedule" ||
    action === "resolve"
  ) {
    return "brand";
  }
  return "neutral";
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Long, unambiguous day header. The audit log is a forensic record,
// so we show weekday + day + month + year (matches the format the
// backend stores in ``created_at``, which is UTC ISO 8601). Using a
// single ``Intl.DateTimeFormat`` instance with an explicit timezone
// keeps the day boundary consistent regardless of the viewer's
// locale.
const dayHeaderFormatter = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

/** ISO date (YYYY-MM-DD) in UTC — used as the grouping key. */
function dayKey(iso: string): string {
  return iso.slice(0, 10);
}

/**
 * Try to map a target_type + target_id pair to a detail page. Falls
 * back to the audit log list (no link) for things we don't expose a
 * drill-in for yet.
 */
function targetHref(targetType: string, targetId: string): string | null {
  switch (targetType) {
    case "ExamSession":
      return `/dashboard/exams/${targetId}`;
    case "Incident":
      return `/dashboard/incident/${targetId}`;
    case "AllocationRun":
      return `/dashboard/allocations/${targetId}`;
    default:
      return null;
  }
}

/**
 * Pretty-print a small JSON object. Truncates to ~12 keys so a
 * huge `before` / `after` doesn't take over the screen.
 */
function formatJson(obj: Record<string, unknown> | null | undefined): string {
  if (!obj || typeof obj !== "object") return "—";
  const keys = Object.keys(obj);
  const truncated = keys.length > 12 ? keys.slice(0, 12) : keys;
  const shown: Record<string, unknown> = {};
  truncated.forEach((k) => {
    shown[k] = obj[k];
  });
  const pretty = JSON.stringify(shown, null, 2);
  if (keys.length > 12) {
    return `${pretty}\n…(${keys.length - 12} more fields)`;
  }
  return pretty;
}

export default function AuditPage() {
  const router = useRouter();
  const [targetType, setTargetType] = useState("");
  const [actionQuery, setActionQuery] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [filterError, setFilterError] = useState<string | null>(null);

  // Build the query string. We pass through every non-empty filter.
  const queryKey = useMemo(
    () =>
      JSON.stringify({
        targetType,
        actionQuery,
        fromDate,
        toDate,
      }),
    [targetType, actionQuery, fromDate, toDate],
  );

  const { data, isLoading, error, refresh } = useFetch(
    () => {
      const params: Record<string, string | number | undefined> = {
        page: 1,
        page_size: 50,
        ordering: "-created_at",
      };
      if (targetType) params.target_type = targetType;
      if (actionQuery.trim()) params.search = actionQuery.trim();
      if (fromDate) params.created_at__gte = `${fromDate}T00:00:00Z`;
      if (toDate) params.created_at__lte = `${toDate}T23:59:59Z`;
      return getAuditLogs(params);
    },
    [queryKey],
  );

  const logs: AuditLog[] = data?.results ?? [];
  const total = data?.count ?? 0;

  // Group logs by UTC day. The backend already returns them sorted
  // by ``-created_at`` so each group is in chronological order.
  // When the user filters to a single day (from == to) the day
  // header is redundant, so we collapse the grouping.
  const grouped = useMemo(() => {
    if (fromDate && toDate && fromDate === toDate) {
      return [{ day: fromDate, label: dayHeaderFormatter.format(new Date(`${fromDate}T00:00:00Z`)), items: logs }];
    }
    const map = new Map<string, AuditLog[]>();
    for (const l of logs) {
      const key = dayKey(l.created_at);
      const arr = map.get(key);
      if (arr) arr.push(l);
      else map.set(key, [l]);
    }
    return Array.from(map.entries()).map(([day, items]) => ({
      day,
      label: dayHeaderFormatter.format(new Date(`${day}T00:00:00Z`)),
      items,
    }));
  }, [logs, fromDate, toDate]);

  // Hide the day header entirely when the window is exactly one
  // day — the section divider would say "Friday" once at the top.
  const showDayHeaders =
    !(fromDate && toDate && fromDate === toDate) && grouped.length > 1;

  const stats = useMemo(() => {
    const actors = new Set<string>();
    const targets = new Set<string>();
    let lastEvent: string | null = null;
    for (const l of logs) {
      if (l.actor_email) actors.add(l.actor_email);
      targets.add(`${l.target_type}:${l.target_id}`);
      if (!lastEvent) lastEvent = l.created_at;
    }
    return {
      total,
      actors: actors.size,
      targets: targets.size,
      lastEvent,
    };
  }, [logs, total]);

  function clearFilters() {
    setTargetType("");
    setActionQuery("");
    setFromDate("");
    setToDate("");
    setFilterError(null);
  }

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <DashboardShell
      title="Audit log"
      subtitle="Every consequential change, immutable"
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
      {error || filterError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Audit log error">
            {filterError ?? error?.message}
          </StatusBanner>
        </div>
      ) : null}

      {/* KPI tiles ----------------------------------------------------- */}
      <StatGrid>
        <Stat
          icon="shield"
          label="Events in window"
          value={String(stats.total)}
          hint="matching current filters"
        />
        <Stat
          icon="users"
          label="Unique actors"
          value={String(stats.actors)}
          hint="on this page"
        />
        <Stat
          icon="document"
          label="Unique targets"
          value={String(stats.targets)}
          hint="this page"
        />
        <Stat
          icon="clock"
          label="Last event"
          value={stats.lastEvent ? fmtTime(stats.lastEvent) : "—"}
          hint={stats.lastEvent ? "most recent" : "no data yet"}
        />
      </StatGrid>

      {/* Filters ------------------------------------------------------- */}
      <Card className="mt-6">
        <CardHeader
          eyebrow="Filters"
          title="Narrow the trail"
          subtitle="Target type, action verb, and date range. The backend filters the source list."
        />
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
              Target type
            </span>
            <select
              value={targetType}
              onChange={(e) => setTargetType(e.target.value)}
              className="mt-1 w-full rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
            >
              {TARGET_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
              Action
            </span>
            <input
              type="search"
              value={actionQuery}
              onChange={(e) => setActionQuery(e.target.value)}
              placeholder="e.g. cancel, publish, login"
              className="mt-1 w-full rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 placeholder:text-ink-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
              From
            </span>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="mt-1 w-full rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
              To
            </span>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="mt-1 w-full rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          </label>
        </div>
        {(targetType || actionQuery || fromDate || toDate) && (
          <div className="mt-4 flex items-center justify-end">
            <Button variant="ghost" size="sm" iconLeft="x" onClick={clearFilters}>
              Clear filters
            </Button>
          </div>
        )}
      </Card>

      {/* List + side rail ---------------------------------------------- */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.5fr_0.5fr]">
        <Card padded={false}>
          <div className="border-b border-ink-100 p-5">
            <CardHeader
              eyebrow="Trail"
              title="Recent events"
              subtitle="Most recent first. Click a row to see the before/after diff."
            />
          </div>

          {logs.length === 0 ? (
            <div className="p-10 text-center text-sm text-ink-500">
              {isLoading
                ? "Loading audit events…"
                : "No audit events match the current filter."}
            </div>
          ) : (
            <div>
              {grouped.map((g) => (
                <section key={g.day}>
                  {showDayHeaders ? (
                    <div className="sticky top-0 z-10 -mx-5 flex items-center gap-3 border-b border-ink-100 bg-surface/95 px-5 py-2.5 backdrop-blur">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200">
                        <Icon name="calendar" className="h-3.5 w-3.5" />
                      </span>
                      <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-700">
                        {g.label}
                      </h4>
                      <span className="text-[11px] text-ink-400">
                        {g.items.length} event{g.items.length === 1 ? "" : "s"}
                      </span>
                    </div>
                  ) : null}
                  <ul className="divide-y divide-ink-100">
                    {g.items.map((l) => {
                      const href = targetHref(l.target_type, l.target_id);
                      const isOpen = expanded.has(l.id);
                      const hasDiff = !!(l.before || l.after);
                      return (
                        <li key={l.id} className="px-5 py-4">
                          <div className="flex items-start gap-3">
                            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-ink-100 text-ink-700 ring-1 ring-inset ring-ink-200">
                              <Icon name="shield" className="h-3.5 w-3.5" />
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge tone={actionTone(l.action)} withDot>
                                  {l.action}
                                </Badge>
                                <span className="text-xs text-ink-500">on</span>
                                <span className="rounded-md bg-ink-100 px-2 py-0.5 font-mono text-xs font-semibold text-ink-700">
                                  {l.target_type}
                                </span>
                                {href ? (
                                  <button
                                    type="button"
                                    onClick={() => router.push(href)}
                                    className="font-mono text-xs text-brand-700 underline-offset-2 hover:underline"
                                    title="Open detail page"
                                  >
                                    {l.target_id.slice(0, 8)}…
                                  </button>
                                ) : (
                                  <span className="font-mono text-xs text-ink-500">
                                    {l.target_id.slice(0, 8)}…
                                  </span>
                                )}
                              </div>
                              <p className="mt-1.5 text-xs text-ink-500">
                                by{" "}
                                <span className="font-semibold text-ink-700">
                                  {l.actor_email ?? "system"}
                                </span>{" "}
                                · {fmtTime(l.created_at)}
                                {l.method && l.path ? (
                                  <>
                                    {" "}
                                    · <span className="font-mono text-[11px]">{l.method}</span>{" "}
                                    <span className="font-mono text-[11px]">{l.path}</span>
                                  </>
                                ) : null}
                              </p>
                            </div>
                            {hasDiff ? (
                              <Button
                                variant="ghost"
                                size="sm"
                                iconRight={isOpen ? "chevron-down" : "chevron-right"}
                                onClick={() => toggleExpand(l.id)}
                              >
                                {isOpen ? "Hide diff" : "Show diff"}
                              </Button>
                            ) : (
                              <span className="text-[11px] text-ink-400">no diff</span>
                            )}
                          </div>
                          {isOpen && hasDiff ? (
                            <div className="mt-3 grid gap-3 lg:grid-cols-2">
                              <div className="rounded-2xl bg-rose-50/60 p-3 ring-1 ring-inset ring-rose-200/60">
                                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-rose-700">
                                  Before
                                </p>
                                <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px] text-ink-700">
                                  {formatJson(l.before)}
                                </pre>
                              </div>
                              <div className="rounded-2xl bg-emerald-50/60 p-3 ring-1 ring-inset ring-emerald-200/60">
                                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-700">
                                  After
                                </p>
                                <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px] text-ink-700">
                                  {formatJson(l.after)}
                                </pre>
                              </div>
                            </div>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-6">
          <CardDark>
            <p className="eyebrow text-brand-300">About the trail</p>
            <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">
              What gets logged
            </h3>
            <p className="mt-2 text-sm text-brand-100/80">
              Every create, update, delete, cancel, reschedule, and lifecycle
              transition is captured automatically. The list below is
              immutable — there's no edit or delete action.
            </p>
            <ul className="mt-4 space-y-2 text-sm text-brand-100/90">
              {(
                [
                  { icon: "check" as IconName, label: "Create / update / delete on every model" },
                  { icon: "alert" as IconName, label: "Lifecycle actions (publish, cancel, …)" },
                  { icon: "user" as IconName, label: "Login, logout, password reset" },
                  { icon: "lightning" as IconName, label: "Engine runs and allocation changes" },
                ]
              ).map((it) => (
                <li key={it.label} className="flex items-start gap-2.5">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/10 text-white">
                    <Icon name={it.icon} className="h-3 w-3" />
                  </span>
                  <span>{it.label}</span>
                </li>
              ))}
            </ul>
          </CardDark>

          <Card>
            <CardHeader eyebrow="Note" title="Read-only" />
            <p className="mt-3 text-sm text-ink-700">
              The audit log is the system of record for "who did what, when".
              For very long histories, export a CSV from the Reports page.
            </p>
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}

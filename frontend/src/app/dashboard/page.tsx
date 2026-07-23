/**
 * Dashboard home — branches by ``primary_role`` to show each role only
 * what they should see.
 *
 * * Operations roles (SA / EO / HoD / Dean) → the full control-room
 *   overview (org-wide KPIs, latest allocation run, today's schedule,
 *   recent incidents). This was the entire page in Phase 10.
 * * INVIGILATOR → "My sessions" tiles + this-week's assignments.
 * * SECURITY_OFFICER → attendance / check-in / open-incident tiles.
 * * STUDENT → "My next exam" + this-week's timetable + notifications.
 *   When the user has no student profile yet, shows a friendly
 *   empty state pointing to the public timetable.
 * * GUEST → public timetable + notification centre. Mostly an entry
 *   point to the public surfaces.
 *
 * The login page already routes everyone to ``/dashboard`` — the
 * branching happens here, not in the login redirect.
 */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { HeroStat, Stat, StatGrid } from "@/components/ui/stat";
import { Icon } from "@/components/ui/icon";
import { ProgressBar, Sparkline } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  clearAuthTokens,
  getAttendanceRoster,
  getDashboardSummary,
  getExamSessions,
  getIncidents,
  getMe,
  logoutRequest,
  type AuthUser,
  type DashboardSummary,
  type ExamSession,
  type Incident,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isOperationsRole } from "@/lib/route-config";
import { useFetch } from "@/lib/use-fetch";

const greetingByHour = (h: number) => {
  if (h < 5) return "Still up?";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 22) return "Good evening";
  return "Late night";
};

const sessionStatusTone: Record<
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

function firstNameOf(fullName: string | null | undefined, email: string | null | undefined): string {
  const source = (fullName || email || "").trim();
  if (!source) return "there";
  // Take the first whitespace-delimited token. For emails like
  // ``alex.smith@x.com`` we keep ``alex.smith`` — friendlier than
  // the full address.
  return source.split(/\s+/)[0]!.split("@")[0]!;
}

export default function DashboardPage() {
  const { user, isReady, refresh: refreshAuth } = useAuth();
  const hour = new Date().getHours();
  const greeting = greetingByHour(hour);
  const firstName = firstNameOf(user?.full_name, user?.email);

  // Refresh the role from the server on mount. The value baked into
  // the JWT at login time can drift (admin demotes themselves via
  // the new set-roles endpoint, a HoD revokes a role, etc.) — using
  // the live ``primary_role`` here keeps the dashboard branch in
  // sync with the backend's RBAC. ``onSuccess`` rewrites localStorage
  // + emits the auth-change event so every subscriber re-renders.
  const { data: liveMe } = useFetch<AuthUser | null>(
    () => getMe().catch(() => null),
    [isReady],
  );
  const liveRole = liveMe?.primary_role ?? liveMe?.role ?? user?.primary_role ?? user?.role;

  if (!isOperationsRole(liveRole)) {
    // Non-operations roles get a personalised, scope-narrow view.
    if (liveRole === "INVIGILATOR") {
      return <InvigilatorOverview greeting={greeting} firstName={firstName} />;
    }
    if (liveRole === "SECURITY_OFFICER") {
      return <SecurityOfficerOverview greeting={greeting} firstName={firstName} />;
    }
    if (liveRole === "STUDENT") {
      return <StudentOverview greeting={greeting} firstName={firstName} />;
    }
    if (liveRole === "GUEST") {
      return <GuestOverview greeting={greeting} firstName={firstName} />;
    }
    // Unrecognised role — still show the operations shell rather
    // than redirect, so the user isn't stranded.
  }

  return <OperationsOverview greeting={greeting} firstName={firstName} refreshAuth={refreshAuth} />;
}

// ===========================================================================
// Operations — admin / EO / HoD / Dean
// ===========================================================================
function OperationsOverview({
  greeting,
  firstName,
  refreshAuth,
}: {
  greeting: string;
  firstName: string;
  refreshAuth: () => void;
}) {
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
      title={`${greeting}, ${firstName === "there" ? "Operations" : firstName}`}
      subtitle="Live control room"
      actions={
        <Button variant="ghost" size="sm" iconLeft="refresh" onClick={() => void refresh()}>
          Refresh
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner
            tone="danger"
            title={
              (error as { status?: number }).status === 401 ||
              (error as { status?: number }).status === 403
                ? "Your session doesn't have access to the operations overview"
                : "Could not load dashboard"
            }
            actions={
              (error as { status?: number }).status === 401 ||
              (error as { status?: number }).status === 403 ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={async () => {
                    try {
                      await logoutRequest();
                    } catch {
                      /* cookie may already be gone */
                    }
                    clearAuthTokens();
                    refreshAuth();
                    // Hard-redirect to /login so the route guard
                    // doesn't bounce back to /dashboard.
                    window.location.href = "/login";
                  }}
                >
                  Sign out
                </Button>
              ) : null
            }
          >
            {(error as { status?: number }).status === 401 ||
            (error as { status?: number }).status === 403
              ? "Your role or sign-in token may have changed since you signed in. Sign out and back in to refresh your access."
              : error.message}
          </StatusBanner>
        </div>
      ) : null}

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

      <StatGrid>
        <Stat
          icon="calendar"
          label="Active period"
          value={data?.active_period?.name ?? (isLoading ? "…" : "—")}
          hint={data?.active_period ? data.active_period.code : "No active period"}
          href="/dashboard/exams"
        />
        <Stat
          icon="users"
          label="Total invigilators"
          value={data ? String(data.total_invigilators) : isLoading ? "…" : "—"}
          hint="registered profiles"
          href="/dashboard/invigilators"
        />
        <Stat
          icon="check"
          label="Sessions scheduled"
          value={data ? String(data.total_sessions) : isLoading ? "…" : "—"}
          hint="across all periods"
          href="/dashboard/timetable"
        />
        <Stat
          icon="alert"
          label="Open incidents"
          value={data ? String(data.total_incidents_open) : isLoading ? "…" : "—"}
          hint="awaiting acknowledgement"
          href="/dashboard/incident"
        />
      </StatGrid>

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
              <HeroStat label="Period" value={latestRun?.period_code ?? "—"} sub="active" />
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

// ===========================================================================
// Invigilator
// ===========================================================================
function InvigilatorOverview({ greeting, firstName }: { greeting: string; firstName: string }) {
  const { data, isLoading, error, refresh } = useFetch(
    () => getExamSessions({ page: 1, page_size: 20, ordering: "starts_at" }),
    [],
  );
  const sessions: ExamSession[] = data?.results ?? [];
  const myUpcoming = sessions.slice(0, 5);

  const today = new Date();
  const todayStr = today.toDateString();
  const todayCount = sessions.filter(
    (s) => new Date(s.starts_at).toDateString() === todayStr,
  ).length;
  const weekFromNow = new Date(today.getTime() + 7 * 86_400_000);
  const weekCount = sessions.filter((s) => {
    const d = new Date(s.starts_at);
    return d >= today && d <= weekFromNow;
  }).length;

  return (
    <DashboardShell
      title={`${greeting}, ${firstName}`}
      subtitle="Your invigilation assignments"
      actions={
        <Button variant="ghost" size="sm" iconLeft="refresh" onClick={() => void refresh()}>
          Refresh
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load sessions">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      <StatGrid>
        <Stat
          icon="calendar"
          label="My sessions today"
          value={String(todayCount)}
          hint={todayCount === 0 ? "You're off today" : "across all rooms"}
          href="/dashboard/timetable"
        />
        <Stat
          icon="clock"
          label="My sessions this week"
          value={String(weekCount)}
          hint="next 7 days"
          href="/dashboard/timetable"
        />
        <Stat
          icon="check"
          label="Readiness"
          value={sessions[0]?.room_code ? "Ready" : isLoading ? "…" : "No sessions"}
          hint={sessions[0]?.room_code ? `Next room: ${sessions[0].room_code}` : "Add a session to begin"}
          href="/dashboard/exams"
        />
        <Stat
          icon="alert"
          label="Open incidents"
          value={String(sessions.filter((s) => s.status === "cancelled").length)}
          hint="cancelled or escalated"
          href="/dashboard/incident"
        />
      </StatGrid>

      <Card className="mt-8" padded={false}>
        <div className="p-6">
          <CardHeader
            eyebrow="My upcoming"
            title="Assigned sessions"
            subtitle="Your next five exam assignments."
            actions={
              <Link href="/dashboard/timetable">
                <Button variant="ghost" size="sm" iconRight="arrow-right">
                  Open timetable
                </Button>
              </Link>
            }
          />
          {myUpcoming.length === 0 ? (
            <div className="mt-6 rounded-2xl border border-dashed border-ink-200 bg-ink-50/40 p-8 text-center text-sm text-ink-500">
              {isLoading
                ? "Loading your assignments…"
                : "No sessions assigned to you yet. Once the engine runs (or you self-allocate), they'll appear here."}
            </div>
          ) : (
            <ul className="mt-6 divide-y divide-ink-100">
              {myUpcoming.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center gap-4 py-3 first:pt-0 last:pb-0"
                >
                  <div className="w-24 shrink-0">
                    <p className="text-sm font-semibold tnum text-ink-900">{dateOf(s.starts_at)}</p>
                    <p className="text-xs text-ink-500">{timeOf(s.starts_at)}</p>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-900">
                      {s.course_code} — {s.course_title}
                    </p>
                    <p className="text-xs text-ink-500">
                      {s.room_code ?? "Room TBC"} · {s.registered}/{s.capacity} candidates
                    </p>
                  </div>
                  <Badge tone={sessionStatusTone[s.status].tone} withDot>
                    {sessionStatusTone[s.status].label}
                  </Badge>
                  <Link href={`/dashboard/exams/${s.id}`}>
                    <Button variant="ghost" size="sm" iconRight="chevron-right">
                      Open
                    </Button>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      <Card className="mt-6">
        <CardHeader
          eyebrow="Need help?"
          title="Before your session"
          subtitle="A quick checklist of what to bring and what to expect."
        />
        <ul className="mt-4 space-y-2 text-sm text-ink-700">
          <li>· Bring your staff ID and a printed copy of the attendance sheet.</li>
          <li>· Arrive 15 minutes before the session start time.</li>
          <li>· Submit an incident from the dashboard if anything unusual happens.</li>
        </ul>
      </Card>
    </DashboardShell>
  );
}

// ===========================================================================
// Security officer
// ===========================================================================
function SecurityOfficerOverview({ greeting, firstName }: { greeting: string; firstName: string }) {
  const { data: sessionsData, isLoading: sessionsLoading } = useFetch(
    () => getExamSessions({ page: 1, page_size: 50, ordering: "starts_at" }),
    [],
  );
  const { data: incidentsData, isLoading: incidentsLoading } = useFetch(
    () => getIncidents({ page: 1, page_size: 5 }),
    [],
  );

  // Live check-in tile: count of invigilators present across the
  // sessions starting in the next 2 hours. We pull a small set of
  // session ids and sum the roster totals client-side. The
  // ``useFetch`` already returns a loading + error state, so the
  // tile degrades to ``—`` on any failure (same behaviour as the
  // hardcoded placeholder it replaced).
  const { data: upcomingForCheckins } = useFetch(
    async () => {
      const list = await getExamSessions({
        page_size: 20,
        ordering: "starts_at",
      }).catch(() => null);
      return list?.results ?? [];
    },
    [],
  );
  const [checkinTotals, setCheckinTotals] = useState<{
    present: number;
    expected: number;
  } | null>(null);
  useEffect(() => {
    let cancelled = false;
    const sessions = (upcomingForCheckins ?? []) as ExamSession[];
    const now = Date.now();
    const twoHours = now + 2 * 60 * 60 * 1000;
    const soon = sessions.filter((s) => {
      const t = new Date(s.starts_at).getTime();
      return t >= now && t <= twoHours;
    });
    if (soon.length === 0) {
      setCheckinTotals({ present: 0, expected: 0 });
      return () => {
        cancelled = true;
      };
    }
    Promise.all(
      soon.map((s) => getAttendanceRoster(s.id).catch(() => null)),
    ).then((rosters) => {
      if (cancelled) return;
      let present = 0;
      let expected = 0;
      for (const r of rosters) {
        if (!r) continue;
        present += r.totals.invigilator.present;
        expected += r.totals.invigilator.expected;
      }
      setCheckinTotals({ present, expected });
    });
    return () => {
      cancelled = true;
    };
  }, [upcomingForCheckins]);

  const sessions: ExamSession[] = sessionsData?.results ?? [];
  const incidents: Incident[] = incidentsData?.results ?? [];
  const todayStr = new Date().toDateString();
  const todayCount = sessions.filter(
    (s) => new Date(s.starts_at).toDateString() === todayStr,
  ).length;
  const openIncidents = incidents.filter(
    (i) => i.status === "open" || i.status === "investigating",
  ).length;

  return (
    <DashboardShell
      title={`${greeting}, ${firstName}`}
      subtitle="Security checkpoint"
    >
      <StatGrid>
        <Stat
          icon="calendar"
          label="Sessions today"
          value={String(todayCount)}
          hint={sessionsLoading ? "Loading…" : "across all rooms"}
          href="/dashboard/timetable"
        />
        <Stat
          icon="check"
          label="Check-ins"
          value={
            checkinTotals && checkinTotals.expected > 0
              ? `${checkinTotals.present} / ${checkinTotals.expected}`
              : "—"
          }
          hint={
            checkinTotals === null
              ? "Loading…"
              : checkinTotals.expected === 0
                ? "No sessions in the next 2 hours"
                : `${checkinTotals.expected - checkinTotals.present} invigilator${
                    checkinTotals.expected - checkinTotals.present === 1
                      ? ""
                      : "s"
                  } still expected`
          }
          href="/dashboard/attendance"
        />
        <Stat
          icon="alert"
          label="Open incidents"
          value={String(openIncidents)}
          hint={incidentsLoading ? "Loading…" : "awaiting triage"}
          href="/dashboard/incident"
        />
        <Stat
          icon="shield"
          label="Active alerts"
          value="0"
          hint="All clear"
          href="/dashboard/incident"
        />
      </StatGrid>

      <Card className="mt-8" padded={false}>
        <div className="p-6">
          <CardHeader
            eyebrow="Live"
            title="Recent incidents"
            subtitle="The latest reports — escalate from the detail page."
            actions={
              <Link href="/dashboard/incident">
                <Button variant="ghost" size="sm" iconRight="arrow-right">
                  Open incident feed
                </Button>
              </Link>
            }
          />
          {incidents.length === 0 ? (
            <p className="mt-6 text-sm text-ink-500">
              {incidentsLoading ? "Loading…" : "No incidents on the wire."}
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
                    <Link href={`/dashboard/incident/${i.id}`}>
                      <Button variant="ghost" size="sm" iconRight="chevron-right">
                        Open
                      </Button>
                    </Link>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </Card>
    </DashboardShell>
  );
}

// ===========================================================================
// Student
// ===========================================================================
function StudentOverview({ greeting, firstName }: { greeting: string; firstName: string }) {
  const { data, isLoading } = useFetch(
    () => getExamSessions({ page: 1, page_size: 20, ordering: "starts_at" }),
    [],
  );
  const sessions: ExamSession[] = data?.results ?? [];
  const next = sessions[0];

  return (
    <DashboardShell
      title={`${greeting}, ${firstName}`}
      subtitle="Your exams at a glance"
    >
      <Card>
        <CardHeader
          eyebrow="Next"
          title="Your next exam"
          subtitle="Live timetable data — refresh to see the latest."
        />
        {next ? (
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-ink-500">Date · Time</p>
              <p className="mt-0.5 text-sm font-semibold tnum text-ink-900">
                {dateOf(next.starts_at)} · {timeOf(next.starts_at)}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-ink-500">Course</p>
              <p className="mt-0.5 text-sm font-semibold text-ink-900">
                {next.course_code} — {next.course_title}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-ink-500">Room</p>
              <p className="mt-0.5 text-sm text-ink-900">{next.room_code ?? "TBC"}</p>
            </div>
            <Badge tone={sessionStatusTone[next.status].tone} withDot>
              {sessionStatusTone[next.status].label}
            </Badge>
            {/* Phase 25 — the student QR card page. The student taps
                this to land on the rotating 60s QR for THIS session.
                Replaces the old "View session" link to /dashboard/exams/[id]
                (which is operations-only and would 403 the student). */}
            <Link href={`/dashboard/student/exams/${next.id}/card`}>
              <Button variant="primary" size="md" iconRight="arrow-right">
                View exam card
              </Button>
            </Link>
          </div>
        ) : (
          <div className="mt-4">
            <StatusBanner tone="info" title="No exams scheduled yet">
              {isLoading
                ? "Loading your timetable…"
                : "Your student profile is being set up. Once it is, your registered sessions will appear here."}
            </StatusBanner>
            <div className="mt-4 flex gap-3">
              <Link href="/dashboard/timetable">
                <Button variant="primary" size="md" iconLeft="calendar">
                  Open public timetable
                </Button>
              </Link>
            </div>
          </div>
        )}
      </Card>

      <Card className="mt-6">
        <CardHeader
          eyebrow="Tip"
          title="Before the exam"
          subtitle="A short list of things to confirm on the day."
        />
        <ul className="mt-4 space-y-2 text-sm text-ink-700">
          <li>· Arrive 15 minutes before the session start time.</li>
          <li>· Bring your student ID and any permitted writing materials.</li>
          <li>· Submit an incident from the dashboard if you spot anything unusual.</li>
        </ul>
      </Card>
    </DashboardShell>
  );
}

// ===========================================================================
// Guest
// ===========================================================================
function GuestOverview({ greeting, firstName }: { greeting: string; firstName: string }) {
  return (
    <DashboardShell
      title={`${greeting}, ${firstName}`}
      subtitle="Public view of the exam timetable"
    >
      <Card>
        <CardHeader
          eyebrow="Welcome"
          title="Public timetable"
          subtitle="The exam timetable is open to everyone. Sign in for personalised views."
        />
        <div className="mt-4 flex gap-3">
          <Link href="/dashboard/timetable">
            <Button variant="primary" size="md" iconLeft="calendar">
              Open the public timetable
            </Button>
          </Link>
        </div>
      </Card>
    </DashboardShell>
  );
}

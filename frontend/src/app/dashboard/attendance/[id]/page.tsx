/**
 * Per-session attendance roster.
 *
 * The door roster view for security officers and the audit
 * view for the operations roles. Renders two tables
 * (invigilators / students) with present / late / expected
 * counts. The "Mark present" button (visible to security only)
 * uses the bulk check-in endpoint to record a single person.
 *
 * The CSV export link opens the backend's
 * ``/attendance/sessions/{id}/export.csv`` URL in a new tab;
 * the cookie auth covers the request.
 */
"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  bulkCheckIn,
  exportAttendanceCsvUrl,
  getAttendanceLive,
  getAttendanceRoster,
  type LiveFeed,
  type Roster,
  type RosterEntry,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { useAuth } from "@/lib/auth";

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

/**
 * The "Live" panel — last 20 check-ins, polled every 5s.
 *
 * This is a Phase 19 addition. The endpoint is
 * ``GET /api/v1/attendance/sessions/{id}/live/`` (20 rows
 * most-recent-first). We poll it on a 5s interval while the
 * page is open. SSE would be nicer but is out of scope for
 * Phase 19.
 *
 * 5s is short enough that a security officer at the door
 * sees a check-in appear within ~6s of the camera
 * submission. Long enough that a room of 10 secops
 * generates only 120 req/min — well within the global
 * 1000/min user throttle.
 */
function LiveFeedPanel({ sessionId }: { sessionId: string }) {
  const [feed, setFeed] = useState<LiveFeed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await getAttendanceLive(sessionId);
        if (cancelled) return;
        setFeed(next);
        setLastUpdated(new Date());
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Could not load live feed");
      }
    };
    void tick();
    const id = window.setInterval(tick, 5_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [sessionId]);

  return (
    <Card padded={false}>
      <div className="flex items-center justify-between border-b border-ink-100 p-5">
        <CardHeader
          eyebrow="Live"
          title="Recent check-ins"
          subtitle="Most recent 20, polled every 5 seconds."
        />
        <div className="flex items-center gap-2 text-[11px] text-ink-500">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          {lastUpdated ? `Updated ${fmtTime(lastUpdated.toISOString())}` : "Loading…"}
        </div>
      </div>
      {error ? (
        <p className="p-6 text-sm text-rose-700">{error}</p>
      ) : !feed ? (
        <p className="p-6 text-sm text-ink-500">Waiting for first scan…</p>
      ) : feed.entries.length === 0 ? (
        <p className="p-6 text-sm text-ink-500">No check-ins yet.</p>
      ) : (
        <ul className="max-h-96 divide-y divide-ink-100 overflow-y-auto">
          {feed.entries.map((e) => (
            <li
              key={e.id}
              className="flex items-center gap-3 px-5 py-2.5 text-sm"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink-100 text-[11px] font-semibold text-ink-700">
                {initialsOf(e.user_name || e.user_email)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink-900">
                  {e.user_name || e.user_email}
                </p>
                <p className="truncate text-xs text-ink-500">
                  {e.user_email}
                  {e.recorded_by_email ? ` · by ${e.recorded_by_email}` : ""}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <Badge
                  tone={
                    e.kind === "invigilator"
                      ? "brand"
                      : e.late
                        ? "warning"
                        : "success"
                  }
                >
                  {e.kind === "invigilator" ? "Staff" : e.late ? "Late" : "Present"}
                </Badge>
                <p className="mt-1 text-[11px] text-ink-400">
                  {fmtTime(e.at)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function RosterTable({
  title,
  rows,
  showMarkPresent,
  onMark,
  pending,
}: {
  title: string;
  rows: RosterEntry[];
  showMarkPresent: boolean;
  onMark?: (entry: RosterEntry) => void;
  pending: string | null;
}) {
  return (
    <Card padded={false}>
      <div className="border-b border-ink-100 p-5">
        <CardHeader eyebrow="Roster" title={title} />
      </div>
      {rows.length === 0 ? (
        <p className="p-6 text-sm text-ink-500">No one on the roster yet.</p>
      ) : (
        <ul className="divide-y divide-ink-100">
          {rows.map((r) => (
            <li
              key={r.user_id}
              className="flex items-center gap-4 px-5 py-3 transition hover:bg-brand-50/30"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white">
                {initialsOf(r.full_name || r.email)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink-900">
                  {r.full_name || r.email || "—"}
                </p>
                <p className="truncate text-xs text-ink-500">
                  {r.email}
                </p>
              </div>
              <div className="shrink-0 text-right">
                {r.present ? (
                  <Badge tone={r.late ? "warning" : "success"} withDot>
                    {r.late ? "Late" : "Present"}
                  </Badge>
                ) : (
                  <Badge tone="neutral">Absent</Badge>
                )}
                <p className="mt-1 text-[11px] text-ink-400">
                  {r.at ? fmtDateTime(r.at) : "—"}
                </p>
              </div>
              {showMarkPresent && !r.present && onMark ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onMark(r)}
                  disabled={pending === r.user_id}
                >
                  {pending === r.user_id ? "…" : "Mark present"}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function AttendanceSessionPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const { user } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingUser, setPendingUser] = useState<string | null>(null);

  const { data, isLoading, error, refresh } = useFetch<Roster | null>(
    async () => (id ? getAttendanceRoster(id) : null),
    [id],
  );

  // Anyone with ``attendance.checkin_any`` can mark present at the
  // door. The backend re-checks this perm on the bulk endpoint.
  const canMarkPresent = Boolean(
    user?.permissions?.includes("attendance.checkin_any"),
  );

  async function markPresent(entry: RosterEntry) {
    if (!id) return;
    setActionError(null);
    setPendingUser(entry.user_id);
    try {
      await bulkCheckIn(id, [
        { user_id: entry.user_id, kind: entry.kind, late: false },
      ]);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setPendingUser(null);
    }
  }

  if (!id) {
    return (
      <DashboardShell title="Attendance" subtitle="Loading…">
        <p className="text-sm text-ink-500">No session id.</p>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell
      title={data?.session ? `${data.session.course_code} — Roster` : "Roster"}
      subtitle={
        data?.session
          ? `${data.session.course_title} · ${fmtTime(
              data.session.starts_at,
            )} – ${fmtTime(data.session.ends_at)}${
              data.session.room_code ? ` · ${data.session.room_code}` : ""
            }`
          : "Loading…"
      }
      actions={
        <div className="flex items-center gap-2">
          {canMarkPresent ? (
            <Button
              variant="primary"
              size="md"
              iconLeft="camera"
              onClick={() => router.push(`/dashboard/attendance/scan?session=${id}`)}
            >
              Scan student
            </Button>
          ) : null}
          <a
            href={exportAttendanceCsvUrl(id)}
            target="_blank"
            rel="noreferrer"
          >
            <Button variant="ghost" size="md" iconLeft="download">
              Export CSV
            </Button>
          </a>
          <Button
            variant="ghost"
            size="md"
            iconLeft="arrow-right"
            onClick={() => router.push("/dashboard/attendance")}
          >
            <span className="-mt-px inline-block rotate-180">Back to attendance</span>
          </Button>
        </div>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load roster">
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

      {isLoading && !data ? (
        <p className="text-sm text-ink-500">Loading roster…</p>
      ) : data ? (
        <>
          <div className="mb-6 grid gap-3 sm:grid-cols-2">
            <Card>
              <p className="eyebrow text-ink-500">Invigilators</p>
              <p className="mt-1 text-3xl font-semibold text-ink-900 tnum">
                {data.totals.invigilator.present} /{" "}
                {data.totals.invigilator.expected}
              </p>
              <p className="mt-1 text-xs text-ink-500">
                {data.totals.invigilator.late} late
              </p>
            </Card>
            <Card>
              <p className="eyebrow text-ink-500">Students</p>
              <p className="mt-1 text-3xl font-semibold text-ink-900 tnum">
                {data.totals.student.present} / {data.totals.student.expected}
              </p>
              <p className="mt-1 text-xs text-ink-500">
                {data.totals.student.late} late
              </p>
            </Card>
          </div>

          <div className="mb-6">
            <LiveFeedPanel sessionId={id} />
          </div>

          <div className="space-y-6">
            <RosterTable
              title="Invigilators"
              rows={data.invigilators}
              showMarkPresent={canMarkPresent}
              onMark={markPresent}
              pending={pendingUser}
            />
            <RosterTable
              title="Students"
              rows={data.students}
              showMarkPresent={canMarkPresent}
              onMark={markPresent}
              pending={pendingUser}
            />
          </div>

          {!canMarkPresent ? (
            <p className="mt-6 flex items-center gap-2 text-xs text-ink-500">
              <Icon name="lock" className="h-3.5 w-3.5" />
              Only the security officer can mark attendees present at the door.
            </p>
          ) : null}
        </>
      ) : (
        <p className="text-sm text-ink-500">No roster yet.</p>
      )}
    </DashboardShell>
  );
}

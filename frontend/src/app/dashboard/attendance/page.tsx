/**
 * Attendance home — the entry point for the security officer (door
 * roster) and a read-only summary for everyone else who can audit
 * attendance (operations roles).
 *
 * Fetches the same ``/exams/sessions/`` list the timetable uses and
 * groups by date. The chip at the top of the date header links to
 * the per-session roster. Invigilators see a different primary
 * entry — the ``/quick`` self check-in shortcut — but this page
 * still works for them (a confirmed-allocation invigilator can
 * still view the door roster of their own session).
 */
"use client";

import Link from "next/link";
import { useMemo } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { getExamSessions, type ExamSession } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { useAuth } from "@/lib/auth";

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDateLong(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    weekday: "long",
    month: "short",
    day: "2-digit",
  });
}

function dayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const statusTone: Record<
  ExamSession["status"],
  "brand" | "success" | "warning" | "neutral" | "danger"
> = {
  draft: "neutral",
  scheduled: "brand",
  ready: "success",
  in_progress: "warning",
  pending: "warning",
  completed: "neutral",
  cancelled: "danger",
};

export default function AttendancePage() {
  const { user } = useAuth();
  const { data, isLoading, error } = useFetch(
    () => getExamSessions({ page_size: 100, ordering: "starts_at" }),
    [],
  );
  const sessions: ExamSession[] = data?.results ?? [];

  // Group by local-time date so the same day on the timetable lines
  // up with the same day here.
  const grouped = useMemo(() => {
    const byDay = new Map<string, ExamSession[]>();
    for (const s of sessions) {
      const k = dayKey(new Date(s.starts_at));
      if (!byDay.has(k)) byDay.set(k, []);
      byDay.get(k)!.push(s);
    }
    return Array.from(byDay.entries()).sort(([a], [b]) =>
      a < b ? -1 : a > b ? 1 : 0,
    );
  }, [sessions]);

  const isInvigilator = user?.primary_role === "INVIGILATOR";

  return (
    <DashboardShell
      title="Attendance"
      subtitle="Check-in events, door roster, exports"
      actions={
        isInvigilator ? (
          <Link href="/dashboard/attendance/quick">
            <Button variant="primary" size="md" iconLeft="check">
              I'm here
            </Button>
          </Link>
        ) : null
      }
    >
      {error ? (
        <div className="mb-6">
          <p className="text-sm text-rose-700">{error.message}</p>
        </div>
      ) : null}

      {isLoading && sessions.length === 0 ? (
        <p className="text-sm text-ink-500">Loading sessions…</p>
      ) : grouped.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-500">
            No exam sessions on the books yet.
          </p>
        </Card>
      ) : (
        <div className="space-y-8">
          {grouped.map(([k, daySessions]) => (
            <section key={k}>
              <CardHeader
                eyebrow={daySessions[0] ? fmtDateLong(daySessions[0].starts_at) : k}
                title={`${daySessions.length} session${
                  daySessions.length === 1 ? "" : "s"
                }`}
                subtitle="Click a session to view the door roster"
              />
              <Card padded={false} className="mt-3">
                <ul className="divide-y divide-ink-100">
                  {daySessions.map((s) => (
                    <li
                      key={s.id}
                      className="flex items-center gap-4 px-5 py-3 transition hover:bg-brand-50/30"
                    >
                      <div className="w-20 shrink-0 text-sm font-semibold text-ink-900 tnum">
                        {fmtTime(s.starts_at)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-ink-900">
                          {s.course_code} — {s.course_title ?? "Untitled"}
                        </p>
                        <p className="text-xs text-ink-500">
                          {s.room_code ?? "No room"} ·{" "}
                          {s.invigilators_required} invigilator
                          {s.invigilators_required === 1 ? "" : "s"} required
                        </p>
                      </div>
                      <Badge tone={statusTone[s.status]} withDot>
                        {s.status.replace("_", " ")}
                      </Badge>
                      <Link
                        href={`/dashboard/attendance/${s.id}`}
                        className="shrink-0"
                      >
                        <Button variant="ghost" size="sm" iconRight="arrow-right">
                          Roster
                        </Button>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ))}
        </div>
      )}

      {!isInvigilator ? (
        <p className="mt-8 flex items-center gap-2 text-xs text-ink-500">
          <Icon name="lightning" className="h-3.5 w-3.5" />
          Invigilators can self check-in from the dedicated{" "}
          <Link
            href="/dashboard/attendance/quick"
            className="font-semibold text-brand-700 underline"
          >
            quick check-in
          </Link>{" "}
          page.
        </p>
      ) : null}
    </DashboardShell>
  );
}

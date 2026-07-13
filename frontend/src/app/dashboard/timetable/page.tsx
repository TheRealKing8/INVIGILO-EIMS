/**
 * Timetable — the day-by-day schedule of every exam session.
 *
 * Reads the full list of exam sessions (page_size=200, ordered by
 * starts_at) and groups them by the local-time date key. Each day
 * card is a Card with a header (date + weekday + session count) and
 * a list of session rows (time / course / room / status / link to
 * the detail page).
 *
 * Filter chips at the top let the user narrow the view to Today /
 * This week / Next week / All. The chip state is just a client-side
 * filter on the already-fetched list — no extra round-trips.
 */
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { StatusBanner } from "@/components/ui/status-banner";
import { getExamSessions, type ExamSession } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

type Range = "today" | "week" | "next_week" | "all";

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

function dayKey(d: Date): string {
  // YYYY-MM-DD in the local time zone — using UTC here would shift
  // the date for users in negative-offset zones. We format parts
  // explicitly to dodge the toISOString trap.
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function fmtDay(iso: string): { weekday: string; date: string; long: string } {
  const d = new Date(iso);
  return {
    weekday: d.toLocaleDateString(undefined, { weekday: "short" }),
    date: d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }),
    long: d.toLocaleDateString(undefined, {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    }),
  };
}

function isInRange(sessionStart: string, range: Range, today: Date): boolean {
  if (range === "all") return true;
  const start = startOfDay(new Date(sessionStart));
  const t = startOfDay(today);
  if (range === "today") return start.getTime() === t.getTime();
  if (range === "week") {
    const weekEnd = new Date(t);
    weekEnd.setDate(weekEnd.getDate() + 7);
    return start >= t && start < weekEnd;
  }
  // next_week
  const next = new Date(t);
  next.setDate(next.getDate() + 7);
  const nextEnd = new Date(t);
  nextEnd.setDate(nextEnd.getDate() + 14);
  return start >= next && start < nextEnd;
}

export default function TimetablePage() {
  const [range, setRange] = useState<Range>("week");

  const { data, isLoading, error, refresh } = useFetch(
    () => getExamSessions({ page_size: 200, ordering: "starts_at" }),
    [],
  );

  const today = useMemo(() => new Date(), []);

  const grouped = useMemo(() => {
    const all = (data?.results ?? []).filter((s) =>
      isInRange(s.starts_at, range, today),
    );
    const map = new Map<string, ExamSession[]>();
    for (const s of all) {
      const k = dayKey(new Date(s.starts_at));
      const list = map.get(k) ?? [];
      list.push(s);
      map.set(k, list);
    }
    // Sort the day-cards chronologically; the sessions inside are
    // already in starts_at order from the backend.
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [data?.results, range, today]);

  const totalShown = grouped.reduce((acc, [, list]) => acc + list.length, 0);

  return (
    <DashboardShell
      title="Exam timetable"
      subtitle="Day-by-day view of every scheduled session"
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
          <StatusBanner tone="danger" title="Could not load the timetable">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      <div className="mb-6 flex flex-wrap items-center gap-2">
        {(
          [
            { value: "today", label: "Today" },
            { value: "week", label: "This week" },
            { value: "next_week", label: "Next week" },
            { value: "all", label: "All" },
          ] as { value: Range; label: string }[]
        ).map((chip) => {
          const active = range === chip.value;
          return (
            <button
              key={chip.value}
              type="button"
              onClick={() => setRange(chip.value)}
              className={[
                "rounded-full px-4 py-1.5 text-sm font-medium transition",
                active
                  ? "bg-brand-700 text-white shadow-[var(--shadow-elev)]"
                  : "bg-surface text-ink-700 ring-1 ring-inset ring-ink-200 hover:bg-ink-100/60",
              ].join(" ")}
            >
              {chip.label}
            </button>
          );
        })}
        <span className="ml-auto text-xs text-ink-500">
          {isLoading ? "Loading…" : `${totalShown} session${totalShown === 1 ? "" : "s"}`}
        </span>
      </div>

      {grouped.length === 0 && !isLoading ? (
        <Card>
          <div className="p-10 text-center text-sm text-ink-500">
            No sessions in this range. Try a different filter or
            <Link href="/dashboard/exams/new" className="ml-1 font-semibold text-brand-700 hover:underline">
              create a new exam
            </Link>
            .
          </div>
        </Card>
      ) : null}

      <div className="space-y-4">
        {grouped.map(([key, sessions]) => {
          const head = fmtDay(sessions[0].starts_at);
          return (
            <Card key={key} padded={false}>
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ink-100 px-5 py-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-700">
                    {head.weekday}
                  </p>
                  <h2 className="text-lg font-semibold text-ink-900">{head.date}</h2>
                </div>
                <Badge tone="brand">
                  {sessions.length} session{sessions.length === 1 ? "" : "s"}
                </Badge>
              </div>
              <ul className="divide-y divide-ink-100">
                {sessions.map((s) => {
                  const tone = statusTone[s.status];
                  return (
                    <li
                      key={s.id}
                      className="flex flex-wrap items-center gap-3 px-5 py-3 transition hover:bg-ink-100/30"
                    >
                      <div className="min-w-[88px]">
                        <p className="text-sm font-semibold tabular-nums text-ink-900">
                          {fmtTime(s.starts_at)} – {fmtTime(s.ends_at)}
                        </p>
                        <p className="text-[11px] text-ink-500 tabular-nums">
                          {s.duration_minutes ?? "—"} min
                        </p>
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-ink-900">
                          {s.course_code ?? "—"} · {s.course_title ?? "Untitled"}
                        </p>
                        <p className="truncate text-xs text-ink-500">
                          {s.room_code ? `Room ${s.room_code}` : "No room"}{" "}
                          {s.building_code ? `· ${s.building_code}` : ""}
                          {s.faculty_code ? ` · ${s.faculty_code}` : ""}
                        </p>
                      </div>
                      <Badge tone={tone.tone}>{tone.label}</Badge>
                      <Link href={`/dashboard/exams/${s.id}`}>
                        <Button variant="ghost" size="sm" iconRight="arrow-right">
                          View
                        </Button>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </Card>
          );
        })}
      </div>
    </DashboardShell>
  );
}

/**
 * Quick check-in — invigilator self-service.
 *
 * Lists upcoming exam sessions in chronological order and shows
 * a big "I'm here" button for each one. The user is the
 * invigilator: tapping the button POSTs to ``/attendance/`` with
 * ``kind=invigilator`` and the session id. The backend enforces
 * the allocation check (403 if the user is not on the session's
 * confirmed allocation list) and the late flag.
 *
 * The page is intentionally minimal — no filters, no edit form.
 * A "back" link returns to the main attendance page.
 */
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { StatusBanner } from "@/components/ui/status-banner";
import { getExamSessions, selfCheckIn, type ExamSession } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { useAuth } from "@/lib/auth";

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "2-digit",
  });
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function QuickCheckInPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [done, setDone] = useState<Set<string>>(new Set());

  const { data, isLoading, error } = useFetch(
    () => getExamSessions({ page_size: 50, ordering: "starts_at" }),
    [],
  );
  const sessions: ExamSession[] = data?.results ?? [];

  // Only future sessions (or sessions starting in the last 30 minutes)
  // are useful here. A past session doesn't need a check-in button —
  // the user is already there or has missed it.
  const upcoming = useMemo(() => {
    const cutoff = Date.now() - 30 * 60 * 1000;
    return sessions
      .filter((s) => new Date(s.starts_at).getTime() >= cutoff)
      .filter((s) => s.status !== "cancelled" && s.status !== "completed");
  }, [sessions]);

  async function checkIn(sessionId: string) {
    setActionError(null);
    setPending(sessionId);
    try {
      await selfCheckIn(sessionId, "invigilator");
      setDone((prev) => {
        const next = new Set(prev);
        next.add(sessionId);
        return next;
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Check-in failed";
      // The most common failure is "not an allocated invigilator on
      // this session" — surface that as a friendly inline message
      // rather than a raw 403.
      setActionError(msg);
    } finally {
      setPending(null);
    }
  }

  return (
    <DashboardShell
      title="Quick check-in"
      subtitle="Tap the session you're arriving at"
      actions={
        <Button
          variant="ghost"
          size="md"
          iconLeft="arrow-right"
          onClick={() => router.push("/dashboard/attendance")}
        >
          <span className="-mt-px inline-block rotate-180">Back to attendance</span>
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
      {actionError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Check-in failed">
            {actionError}
          </StatusBanner>
        </div>
      ) : null}

      {!user ? (
        <Card>
          <p className="text-sm text-ink-500">Loading…</p>
        </Card>
      ) : user.primary_role !== "INVIGILATOR" ? (
        <Card>
          <CardHeader
            eyebrow="Heads up"
            title="This page is for invigilators"
            subtitle="If you arrived at a session and need to be marked present, ask the security officer at the door."
          />
        </Card>
      ) : isLoading && upcoming.length === 0 ? (
        <p className="text-sm text-ink-500">Loading your sessions…</p>
      ) : upcoming.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-500">
            Nothing to check in to. Your upcoming sessions will show up here
            when they're scheduled.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {upcoming.map((s) => {
            const isDone = done.has(s.id);
            return (
              <Card key={s.id} padded={false}>
                <div className="flex items-center gap-4 p-5">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-ink-900">
                      {s.course_code} — {s.course_title ?? "Untitled"}
                    </p>
                    <p className="mt-1 text-xs text-ink-500">
                      {fmtDate(s.starts_at)} · {fmtTime(s.starts_at)} –{" "}
                      {fmtTime(s.ends_at)}
                      {s.room_code ? ` · ${s.room_code}` : ""}
                    </p>
                  </div>
                  {isDone ? (
                    <Badge tone="success" withDot>
                      Checked in
                    </Badge>
                  ) : (
                    <Button
                      variant="primary"
                      size="md"
                      iconLeft="check"
                      onClick={() => void checkIn(s.id)}
                      disabled={pending === s.id}
                    >
                      {pending === s.id ? "Checking in…" : "I'm here"}
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <p className="mt-8 flex items-center gap-2 text-xs text-ink-500">
        <Icon name="clock" className="h-3.5 w-3.5" />
        The 10-minute grace window means arriving up to 10 minutes after
        the start is still recorded as on time.
      </p>
      <p className="mt-2 flex items-center gap-2 text-xs text-ink-500">
        <Icon name="arrow-right" className="h-3.5 w-3.5 -rotate-45" />
        Looking for the full roster view?{" "}
        <Link
          href="/dashboard/attendance"
          className="font-semibold text-brand-700 underline"
        >
          Go to attendance
        </Link>
        .
      </p>
    </DashboardShell>
  );
}

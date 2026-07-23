/**
 * Student QR card — the "show this at the door" page.
 *
 * Phase 25. A signed-in STUDENT taps into a session from their
 * dashboard or the public timetable and lands here. The page
 * fetches *their* StudentRegistration row for that exam session
 * and renders the rotating 60s QR PNG that the door scanner
 * reads.
 *
 * The page is intentionally self-contained: it does not require
 * the parent exam session to be loaded before showing the card.
 * If the registration row exists, the card is what the student
 * needs. If it doesn't, an empty state explains why and points
 * them at the timetable.
 *
 * The 60s rotation is client-driven: a ``useState(Date.now())`` +
 * a 60-second ``setInterval`` bumps a cache-busting ``?t=`` query
 * param on the ``<img src>``, which forces the browser to
 * re-fetch the PNG (and the server to mint a fresh signed
 * token). The same pattern is used for the staff QR panel at
 * ``/dashboard/invigilators/[id]`` — see Phase 19.
 *
 * The backend's ``get_queryset`` (Phase 25) narrows the
 * registration queryset to ``student == request.user`` for
 * narrow readers, so a student can never fetch another
 * student's row. The page does not need to second-guess that
 * contract — it asks the backend for the row by id and lets a
 * 404 surface the "not yours" path.
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
  getExamSession,
  getMyRegistrationForSession,
  studentRegistrationQrUrl,
  type ExamSession,
  type StudentRegistration,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/use-fetch";

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDayLong(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function durationMinutes(start: string, end: string): number {
  return Math.round(
    (new Date(end).getTime() - new Date(start).getTime()) / 60000,
  );
}

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

export default function StudentExamCardPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const { user } = useAuth();

  // Fetch the registration row + the parent session in parallel.
  // ``useFetch`` re-runs when its deps array changes; the page
  // re-fetches when the URL id changes (so back/forward work).
  const {
    data: registration,
    isLoading: regLoading,
    error: regError,
  } = useFetch<StudentRegistration | null>(
    async () => {
      if (!id || !user?.id) return null;
      return getMyRegistrationForSession(user.id, id);
    },
    [id, user?.id],
  );

  const {
    data: session,
    isLoading: sessionLoading,
    error: sessionError,
  } = useFetch<ExamSession | null>(
    async () => (id ? getExamSession(id) : null),
    [id],
  );

  // QR cache-buster — the same pattern as StaffQrPanel. The src
  // changes every 60s, which makes the browser re-fetch the PNG;
  // each fetch mints a fresh signed token on the server.
  const [stamp, setStamp] = useState<number>(() => Date.now());
  useEffect(() => {
    if (!registration) return;
    const handle = window.setInterval(() => setStamp(Date.now()), 60_000);
    return () => window.clearInterval(handle);
  }, [registration]);

  const isLoading = regLoading || sessionLoading;
  const error = regError ?? sessionError;

  // ----- Render ----------------------------------------------------------
  return (
    <DashboardShell
      title="My exam card"
      subtitle="Show this QR code at the door for a quick check-in"
      actions={
        <Button
          variant="ghost"
          size="md"
          iconLeft="arrow-right"
          onClick={() => router.push("/dashboard")}
        >
          <span className="-mt-px inline-block rotate-180">Back to dashboard</span>
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load your exam card">
            {(error as Error).message ?? "Please try again."}
          </StatusBanner>
        </div>
      ) : null}

      {isLoading && !registration ? (
        <Card>
          <p className="text-sm text-ink-500">Loading your exam card…</p>
        </Card>
      ) : !registration ? (
        <Card>
          <CardHeader
            eyebrow="No card yet"
            title="You are not registered for this exam"
            subtitle="If you believe this is a mistake, contact your examination office."
          />
          <div className="mt-4">
            <StatusBanner tone="info" title="What to do next">
              Check the public timetable to see whether registrations for this
              session are still open, or wait for your EO to publish a roster
              that includes you.
            </StatusBanner>
            <div className="mt-4 flex gap-3">
              <Button
                variant="primary"
                size="md"
                iconLeft="calendar"
                onClick={() => router.push("/dashboard/timetable")}
              >
                Open timetable
              </Button>
              <Button
                variant="ghost"
                size="md"
                onClick={() => router.push("/dashboard")}
              >
                Back to dashboard
              </Button>
            </div>
          </div>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          {/* The QR card. ------------------------------------------------ */}
          <Card>
            <CardHeader
              eyebrow="My exam card"
              title="Show this at the door"
              subtitle="Rotates every 60 seconds. Tied to your account — don't share it."
            />
            <div className="mt-4 flex justify-center rounded-2xl bg-white p-4 ring-1 ring-ink-200">
              <img
                src={`${studentRegistrationQrUrl(registration.id)}?t=${stamp}`}
                alt="Exam QR code"
                width={192}
                height={192}
                className="h-48 w-48"
              />
            </div>
            <p className="mt-3 text-xs text-ink-500">
              The security officer scans this with the door scanner; the
              scanner checks the signature and creates a check-in. 60-second
              rotation, signed token — a screenshot becomes useless within a
              minute.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Badge tone="brand" withDot>
                Code · {registration.student_code}
              </Badge>
              <span className="text-xs text-ink-500">
                Or type this code into the scanner if the QR is unreadable.
              </span>
            </div>
          </Card>

          {/* The session details. --------------------------------------- */}
          <Card>
            <CardHeader
              eyebrow="Session"
              title={session ? session.course_title ?? "Exam session" : "Exam session"}
              subtitle={
                session
                  ? `${session.course_code ?? ""} · ${session.period_code ?? ""}`.trim()
                  : ""
              }
            />
            {session ? (
              <dl className="mt-5 grid gap-4 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                    Date
                  </dt>
                  <dd className="mt-1 text-sm font-semibold text-ink-900">
                    {fmtDayLong(session.starts_at)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                    Time
                  </dt>
                  <dd className="mt-1 text-sm font-semibold tnum text-ink-900">
                    {fmtTime(session.starts_at)} – {fmtTime(session.ends_at)}
                    <span className="ml-2 text-xs font-normal text-ink-500">
                      ({durationMinutes(session.starts_at, session.ends_at)} min)
                    </span>
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                    Room
                  </dt>
                  <dd className="mt-1 inline-flex items-center gap-2 text-sm text-ink-900">
                    <Icon name="map-pin" className="h-3.5 w-3.5 text-ink-400" />
                    {session.room_code ?? "TBC"}
                    {session.building_code ? (
                      <span className="text-xs text-ink-500">
                        · {session.building_code}
                      </span>
                    ) : null}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                    Status
                  </dt>
                  <dd className="mt-1">
                    <Badge tone={statusTone[session.status].tone} withDot>
                      {statusTone[session.status].label}
                    </Badge>
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="mt-4 text-sm text-ink-500">
                Session details are loading…
              </p>
            )}

            {session?.special_requirements ? (
              <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50/60 p-4 text-sm text-amber-900">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-700">
                  Bring with you
                </p>
                <p className="mt-1">{session.special_requirements}</p>
              </div>
            ) : null}
          </Card>
        </div>
      )}
    </DashboardShell>
  );
}

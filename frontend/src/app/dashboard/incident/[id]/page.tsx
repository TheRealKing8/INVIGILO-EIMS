/**
 * Incident detail — drill-in from the /dashboard/incident feed.
 *
 * Shows the full incident body, the timeline (reported/resolved),
 * and a cross-link to the related exam session (when the incident
 * is attached to one). The status select on the right updates
 * `set-status/` on the backend and refreshes the page in place —
 * the same UX as the parent list's inline select.
 */
"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { Icon, type IconName } from "@/components/ui/icon";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  getExamSession,
  getIncident,
  updateIncidentStatus,
  type ExamSession,
  type Incident,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

type Status = Incident["status"];

const severityTone: Record<
  Incident["severity"],
  { tone: "neutral" | "warning" | "danger" | "info"; label: string; bg: string; ring: string }
> = {
  low: { tone: "neutral", label: "Low", bg: "bg-ink-100", ring: "ring-ink-200" },
  medium: { tone: "warning", label: "Medium", bg: "bg-amber-50", ring: "ring-amber-200" },
  high: { tone: "danger", label: "High", bg: "bg-rose-50", ring: "ring-rose-200" },
  critical: { tone: "info", label: "Critical", bg: "bg-rose-100", ring: "ring-rose-300" },
};

const statusTone: Record<
  Status,
  { tone: "danger" | "warning" | "success" | "brand"; label: string }
> = {
  open: { tone: "danger", label: "Open" },
  investigating: { tone: "warning", label: "Investigating" },
  escalated: { tone: "warning", label: "Escalated" },
  resolved: { tone: "success", label: "Resolved" },
};

function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function initialsOf(name: string | undefined | null): string {
  if (!name) return "??";
  return name
    .split(/\s+/)
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export default function IncidentDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [statusError, setStatusError] = useState<string | null>(null);
  const [pendingStatus, setPendingStatus] = useState<Status | null>(null);

  const { data, isLoading, error, refresh } = useFetch<{
    incident: Incident | null;
    session: ExamSession | null;
  }>(
    async () => {
      if (!id) return { incident: null, session: null };
      const incident = await getIncident(id).catch(() => null);
      const sessionId = incident?.session;
      const session = sessionId
        ? await getExamSession(sessionId).catch(() => null)
        : null;
      return { incident, session };
    },
    [id],
  );

  const incident = data?.incident ?? null;
  const session = data?.session ?? null;

  async function handleStatusChange(next: Status) {
    if (!incident) return;
    setStatusError(null);
    setPendingStatus(next);
    try {
      await updateIncidentStatus(incident.id, next);
      await refresh();
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : "Status update failed");
    } finally {
      setPendingStatus(null);
    }
  }

  const sev = incident ? severityTone[incident.severity] : null;

  return (
    <DashboardShell
      title={incident ? incident.title : "Incident"}
      subtitle={
        incident
          ? `Reported ${fmtDateTime(incident.reported_at)}`
          : "Loading incident…"
      }
      actions={
        <Button
          variant="ghost"
          size="md"
          iconLeft="arrow-right"
          onClick={() => router.push("/dashboard/incident")}
        >
          <span className="-mt-px inline-block rotate-180">Back to incidents</span>
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load incident">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      {statusError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Status update failed">
            {statusError}
          </StatusBanner>
        </div>
      ) : null}

      {/* Header + status control ----------------------------------- */}
      <Card className="mb-6">
        {isLoading && !incident ? (
          <p className="text-sm text-ink-500">Loading incident…</p>
        ) : incident && sev ? (
          <div className="grid gap-5 lg:grid-cols-[1fr_auto]">
            <div>
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-12 w-12 items-center justify-center rounded-2xl ${sev.bg} ${sev.ring} ring-1 ring-inset`}
                >
                  <Icon name="alert" className="h-5 w-5 text-ink-700" />
                </span>
                <div>
                  <p className="eyebrow text-ink-500">Incident</p>
                  <h2 className="mt-1 text-2xl font-semibold text-ink-900">
                    {incident.title}
                  </h2>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Badge tone={sev.tone} className="uppercase">
                  {sev.label} severity
                </Badge>
                <Badge tone={statusTone[incident.status].tone} withDot>
                  {statusTone[incident.status].label}
                </Badge>
                {incident.session_code ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold text-brand-800 ring-1 ring-inset ring-brand-100">
                    <Icon name="map-pin" className="h-3 w-3" />
                    {incident.session_code}
                  </span>
                ) : null}
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <label className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Set status
              </label>
              <select
                value={incident.status}
                onChange={(e) => void handleStatusChange(e.target.value as Status)}
                disabled={pendingStatus !== null}
                className="rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              >
                <option value="open">Open</option>
                <option value="investigating">Investigating</option>
                <option value="escalated">Escalated</option>
                <option value="resolved">Resolved</option>
              </select>
              {pendingStatus ? (
                <span className="text-[11px] text-ink-400">Updating…</span>
              ) : null}
            </div>
          </div>
        ) : (
          <p className="text-sm text-ink-500">Incident not found.</p>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        {/* Body + Timeline ------------------------------------------- */}
        <div className="space-y-6">
          <Card>
            <CardHeader
              eyebrow="Description"
              title="What was reported"
              subtitle="The full text the invigilator submitted."
            />
            <div className="mt-4">
              {incident?.body ? (
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
                  {incident.body}
                </p>
              ) : (
                <p className="text-sm italic text-ink-500">
                  No additional details provided.
                </p>
              )}
            </div>
          </Card>

          <Card padded={false}>
            <div className="border-b border-ink-100 p-5">
              <CardHeader
                eyebrow="Lifecycle"
                title="Timeline"
                subtitle="From report to resolution."
              />
            </div>
            <ol className="divide-y divide-ink-100">
              <li className="flex items-start gap-3 px-5 py-4">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200">
                  <Icon name="alert" className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-ink-900">Reported</p>
                  <p className="mt-0.5 text-xs text-ink-500">
                    {fmtDateTime(incident?.reported_at)} · by{" "}
                    <span className="font-semibold text-ink-700">
                      {incident?.reporter_name ?? incident?.reporter_email ?? "Anonymous"}
                    </span>
                  </p>
                </div>
              </li>
              <li className="flex items-start gap-3 px-5 py-4">
                <span
                  className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-1 ring-inset ${
                    incident?.status === "resolved"
                      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                      : "bg-ink-100 text-ink-500 ring-ink-200"
                  }`}
                >
                  <Icon
                    name={incident?.status === "resolved" ? "check" : "clock"}
                    className="h-4 w-4"
                  />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-ink-900">
                    {incident?.status === "resolved" ? "Resolved" : "In progress"}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-500">
                    {incident?.resolved_at
                      ? `${fmtDateTime(incident.resolved_at)} · by ${incident.resolved_by_email ?? "—"}`
                      : "Awaiting resolution."}
                  </p>
                </div>
              </li>
            </ol>
          </Card>
        </div>

        {/* Related session + tips ------------------------------------ */}
        <div className="space-y-6">
          <CardDark>
            <p className="eyebrow text-brand-300">Linked session</p>
            {session ? (
              <>
                <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">
                  {session.course_code}
                </h3>
                <p className="mt-1 text-sm text-brand-100/80">
                  {session.course_title ?? "Exam session"}
                </p>
                <dl className="mt-4 space-y-2 text-sm text-brand-100/90">
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-brand-200/70">When</dt>
                    <dd className="tnum text-white">
                      {fmtDateTime(session.starts_at)}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-brand-200/70">Time</dt>
                    <dd className="tnum text-white">
                      {fmtTime(session.starts_at)} – {fmtTime(session.ends_at)}
                    </dd>
                  </div>
                  {session.room_code ? (
                    <div className="flex items-center justify-between gap-3">
                      <dt className="text-brand-200/70">Room</dt>
                      <dd className="text-white">{session.room_code}</dd>
                    </div>
                  ) : null}
                </dl>
                <Button
                  variant="light"
                  size="md"
                  iconRight="arrow-right"
                  className="mt-5"
                  fullWidth
                  onClick={() => router.push(`/dashboard/exams/${session.id}`)}
                >
                  Open session detail
                </Button>
              </>
            ) : (
              <>
                <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">
                  Not linked
                </h3>
                <p className="mt-2 text-sm text-brand-100/80">
                  This incident was filed without a session. It may be a
                  pre-emptive flag or a general field report.
                </p>
                <div className="mt-5 flex items-center gap-2 text-xs text-brand-200/70">
                  <Icon name="user" className="h-3.5 w-3.5" />
                  <span>
                    Reported by{" "}
                    <span className="font-semibold text-white">
                      {incident?.reporter_name ?? incident?.reporter_email ?? "Anonymous"}
                    </span>
                  </span>
                </div>
              </>
            )}
          </CardDark>

          {incident?.reporter_email ? (
            <Card>
              <CardHeader eyebrow="Reporter" title="Who filed this" />
              <div className="mt-4 flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white">
                  {initialsOf(incident.reporter_name ?? incident.reporter_email)}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-ink-900">
                    {incident.reporter_name ?? "—"}
                  </p>
                  <p className="truncate text-xs text-ink-500">
                    {incident.reporter_email}
                  </p>
                </div>
              </div>
            </Card>
          ) : null}

          <Card>
            <CardHeader eyebrow="Reminder" title="Response playbook" />
            <ul className="mt-4 space-y-2.5 text-sm text-ink-700">
              {(
                [
                  { icon: "alert" as IconName, label: "Open → acknowledge within 5 minutes." },
                  { icon: "clock" as IconName, label: "Investigating → update every 30 minutes." },
                  { icon: "arrow-up-right" as IconName, label: "Escalate when the issue is exam-wide." },
                  { icon: "check" as IconName, label: "Resolve only after the room is steady." },
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

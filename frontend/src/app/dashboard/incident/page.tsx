/**
 * Incidents module — live log of reports from the field.
 *
 * Reads `getIncidents` and lets the user surface a draft via
 * a lightweight inline form (no modal — matches the page's
 * existing visual rhythm). Filter buttons collapse to a
 * `status` query param on re-fetch.
 */
"use client";

import { useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { MiniBar } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  createIncident,
  getIncidents,
  updateIncidentStatus,
  type Incident,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

type Severity = Incident["severity"];
type Status = Incident["status"];

const severityTone: Record<
  Severity,
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

const filters: { label: string; status?: Status }[] = [
  { label: "All" },
  { label: "Open", status: "open" },
  { label: "Investigating", status: "investigating" },
  { label: "Resolved", status: "resolved" },
];

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function IncidentPage() {
  const [filter, setFilter] = useState<typeof filters[number]>(filters[0]);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftSeverity, setDraftSeverity] = useState<Severity>("medium");
  const [posting, setPosting] = useState(false);
  const [postError, setPostError] = useState<string | null>(null);

  const { data, isLoading, error, refresh } = useFetch(
    () => getIncidents({ page: 1, page_size: 50, ...(filter.status ? { status: filter.status } : {}) }),
    [filter.status],
  );

  const incidents = data?.results ?? [];

  // Severity counts for the CardDark summary (last 7-day proxy).
  const bySeverity = incidents.reduce<Record<Severity, number>>(
    (acc, i) => {
      acc[i.severity] = (acc[i.severity] ?? 0) + 1;
      return acc;
    },
    { low: 0, medium: 0, high: 0, critical: 0 },
  );
  const urgent = (bySeverity.high ?? 0) + (bySeverity.critical ?? 0);
  const resolved = bySeverity ? (bySeverity.low ?? 0) : 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draftTitle.trim()) return;
    setPosting(true);
    setPostError(null);
    try {
      await createIncident({
        title: draftTitle.trim(),
        severity: draftSeverity,
      });
      setDraftTitle("");
      setDraftSeverity("medium");
      await refresh();
    } catch (err) {
      setPostError(err instanceof Error ? err.message : String(err));
    } finally {
      setPosting(false);
    }
  }

  async function handleStatusChange(id: string, status: Status) {
    try {
      await updateIncidentStatus(id, status);
      await refresh();
    } catch (err) {
      setPostError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <DashboardShell
      title="Incidents"
      subtitle="Live log · Escalations · Resolution"
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
      {error || postError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Incidents error">
            {postError ?? error?.message}
          </StatusBanner>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <Card padded={false}>
          <div className="flex items-center justify-between border-b border-ink-100 p-5">
            <CardHeader
              eyebrow="Live"
              title="Incident feed"
              subtitle="Most recent first. Click an incident to drill into the full record."
            />
            <div className="flex items-center gap-2">
              {filters.map((f) => (
                <button
                  key={f.label}
                  className={[
                    "rounded-full px-3 py-1.5 text-sm font-medium transition",
                    filter.label === f.label
                      ? "bg-brand-700 text-white"
                      : "bg-ink-100 text-ink-700 hover:bg-ink-200",
                  ].join(" ")}
                  onClick={() => setFilter(f)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Inline composer */}
          <form
            onSubmit={handleSubmit}
            className="grid grid-cols-[1fr_auto_auto] items-end gap-2 border-b border-ink-100 p-5"
          >
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                New incident
              </span>
              <input
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                placeholder="e.g. Late invigilator, projector failure"
                className="mt-1 w-full rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 placeholder:text-ink-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              />
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Severity
              </span>
              <select
                value={draftSeverity}
                onChange={(e) => setDraftSeverity(e.target.value as Severity)}
                className="mt-1 rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </label>
            <Button variant="primary" size="md" iconLeft="plus" disabled={posting || !draftTitle.trim()} type="submit">
              {posting ? "Posting…" : "Log incident"}
            </Button>
          </form>

          {incidents.length === 0 ? (
            <div className="p-10 text-center text-sm text-ink-500">
              {isLoading ? "Loading incidents…" : "No incidents match the current filter."}
            </div>
          ) : (
            <ul className="divide-y divide-ink-100">
              {incidents.map((i) => {
                const sev = severityTone[i.severity];
                return (
                  <li
                    key={i.id}
                    className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-4 px-5 py-4 transition hover:bg-brand-50/30"
                  >
                    <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${sev.bg} ${sev.ring} ring-1 ring-inset`}>
                      <Icon name="alert" className="h-4 w-4 text-ink-700" />
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-ink-900">{i.title}</p>
                        <Badge tone={sev.tone} className="uppercase">{sev.label}</Badge>
                      </div>
                      <p className="mt-0.5 text-xs text-ink-500">
                        {i.session_code ?? "No session"} · Reported by {i.reporter_email ?? "Anonymous"} · {fmtTime(i.reported_at)}
                      </p>
                    </div>
                    <select
                      value={i.status}
                      onChange={(e) => void handleStatusChange(i.id, e.target.value as Status)}
                      className="rounded-lg border border-ink-200 bg-surface px-2 py-1 text-xs text-ink-700 focus:border-brand-500 focus:outline-none"
                    >
                      <option value="open">Open</option>
                      <option value="investigating">Investigating</option>
                      <option value="escalated">Escalated</option>
                      <option value="resolved">Resolved</option>
                    </select>
                    <Badge tone={statusTone[i.status].tone} withDot>
                      {statusTone[i.status].label}
                    </Badge>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <div className="space-y-6">
          <CardDark>
            <p className="eyebrow text-brand-300">Response status</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">
              Escalation workflow
            </h3>
            <p className="mt-2 text-sm text-brand-100/80">
              Each incident flows from invigilator → chief invigilator → exam
              officer, with full ownership and timestamp trail.
            </p>
            <div className="mt-5 grid grid-cols-2 gap-3">
              {[
                { label: "Urgent cases", value: String(urgent) },
                {
                  label: "Resolved",
                  value: String(incidents.filter((i) => i.status === "resolved").length),
                },
                { label: "Open", value: String(incidents.filter((i) => i.status === "open").length) },
                { label: "Investigating", value: String(incidents.filter((i) => i.status === "investigating").length) },
              ].map((s) => (
                <div
                  key={s.label}
                  className="rounded-2xl bg-white/[0.04] p-4 ring-1 ring-inset ring-white/10"
                >
                  <p className="text-2xl font-semibold tnum text-white">{s.value}</p>
                  <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-200/80">
                    {s.label}
                  </p>
                </div>
              ))}
            </div>
          </CardDark>

          <Card>
            <CardHeader eyebrow="By severity" title="This page" />
            <div className="mt-5">
              <MiniBar
                values={[
                  bySeverity.low ?? 0,
                  bySeverity.medium ?? 0,
                  bySeverity.high ?? 0,
                  bySeverity.critical ?? 0,
                ]}
                labels={["Low", "Medium", "High", "Critical"]}
                tone="danger"
              />
            </div>
            <div className="mt-4 flex items-center justify-between text-xs text-ink-500">
              <span>{incidents.length} incidents on this page</span>
            </div>
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}

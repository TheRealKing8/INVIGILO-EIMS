/**
 * Invigilators module — roster, availability, workload.
 *
 * Reads `getInvigilators` and renders live data. When no
 * profiles are registered yet, shows the empty state.
 */
"use client";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { CardDark } from "@/components/ui/card";
import { ProgressBar, Sparkline } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import { getInvigilators, type InvigilatorProfile } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

function initialsOf(name: string | undefined): string {
  if (!name) return "??";
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export default function InvigilatorsPage() {
  const { data, isLoading, error, refresh } = useFetch(() =>
    getInvigilators({ page: 1, page_size: 50 }),
  );

  const people = data?.results ?? [];
  const total = data?.count ?? 0;
  const active = people.filter((p) => p.is_active).length;

  return (
    <DashboardShell
      title="Invigilators"
      subtitle="Roster · Availability · Workload"
      actions={
        <>
          <Button
            variant="ghost"
            size="md"
            iconLeft="refresh"
            onClick={() => void refresh()}
          >
            Refresh
          </Button>
          <Button variant="primary" size="md" iconLeft="plus">
            Add invigilator
          </Button>
        </>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load invigilators">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Total staff", value: total ? String(total) : isLoading ? "…" : "0", delta: "registered profiles" },
          { label: "Active on this page", value: String(active), delta: `${people.length} loaded` },
          { label: "Avg. max sessions", value: people.length ? (people.reduce((s, p) => s + p.max_sessions_per_cycle, 0) / people.length).toFixed(1) : "—", delta: "per cycle" },
          { label: "Avg. rating", value: people.length ? (people.reduce((s, p) => s + parseFloat(p.rating || "0"), 0) / people.length).toFixed(2) : "—", delta: "across roster" },
        ].map((s) => (
          <div
            key={s.label}
            className="rounded-3xl bg-surface p-5 ring-1 ring-ink-200 shadow-[var(--shadow-card)]"
          >
            <p className="text-sm text-ink-500">{s.label}</p>
            <p className="mt-2 text-3xl font-semibold tnum text-ink-900">{s.value}</p>
            <p className="mt-1 text-xs text-ink-500">{s.delta}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.5fr_0.5fr]">
        <Card padded={false}>
          <div className="flex items-center justify-between border-b border-ink-100 p-5">
            <CardHeader
              eyebrow="Roster"
              title="Staff directory"
              subtitle="Click a person to see their assignments, workload, and rating."
            />
            <Button variant="ghost" size="sm" iconLeft="search">Search</Button>
          </div>

          {people.length === 0 ? (
            <div className="p-10 text-center text-sm text-ink-500">
              {isLoading ? "Loading invigilators…" : "No invigilators registered yet. Add one to get started."}
            </div>
          ) : (
            <ul className="divide-y divide-ink-100">
              {people.map((p: InvigilatorProfile) => (
                <li
                  key={p.id}
                  className="flex items-center gap-4 px-5 py-4 transition hover:bg-brand-50/30"
                >
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-700 text-sm font-semibold text-white">
                    {initialsOf(p.user_full_name ?? p.user_email)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-ink-900">
                      {p.user_full_name ?? p.user_email ?? "Invigilator"}
                    </p>
                    <p className="text-xs text-ink-500">
                      {p.primary_department_code ?? p.primary_department ?? "—"} · max {p.max_sessions_per_cycle} sessions/cycle
                    </p>
                  </div>
                  <div className="hidden w-32 text-right sm:block">
                    <p className="text-xs text-ink-500">Max / cycle</p>
                    <p className="text-sm font-semibold tnum text-ink-900">{p.max_sessions_per_cycle}</p>
                  </div>
                  <div className="hidden w-28 text-right sm:block">
                    <p className="text-xs text-ink-500">Rating</p>
                    <p className="text-sm font-semibold tnum text-ink-900">
                      {parseFloat(p.rating || "0").toFixed(1)} ★
                    </p>
                  </div>
                  <Badge tone={p.is_active ? "success" : "neutral"} withDot>
                    {p.is_active ? "Active" : "Inactive"}
                  </Badge>
                  <Button variant="ghost" size="sm" iconRight="chevron-right">
                    Open
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader eyebrow="Workload" title="Cycle cap utilisation" />
            <div className="mt-5 space-y-4">
              {people.length === 0 ? (
                <p className="text-sm text-ink-500">No data yet.</p>
              ) : (
                people.slice(0, 5).map((p) => {
                  const cap = Math.max(p.max_sessions_per_cycle, 1);
                  // We don't have current load — show max cap as the denominator.
                  return (
                    <div key={p.id}>
                      <div className="flex items-center justify-between text-xs text-ink-700">
                        <span className="font-medium">{p.user_full_name ?? p.user_email ?? "—"}</span>
                        <span className="tnum text-ink-500">cap {p.max_sessions_per_cycle}</span>
                      </div>
                      <ProgressBar
                        value={100}
                        tone="brand"
                        className="mt-1.5"
                      />
                    </div>
                  );
                })
              )}
            </div>
          </Card>

          <CardDark>
            <p className="eyebrow text-brand-300">Auto-assignment</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">Ready to run</h3>
            <p className="mt-2 text-sm text-brand-100/80">
              Generate a fresh allocation in under 10 seconds. INVIGILO
              honours every constraint you set.
            </p>
            <div className="mt-5">
              <Sparkline
                values={[68, 72, 80, 76, 88, 92, 95, 98]}
                tone="success"
                width={220}
                height={48}
              />
            </div>
            <p className="mt-2 text-[11px] text-brand-200/70">
              {total ? `${total} registered profiles ready` : "Register invigilators to begin"}
            </p>
            <Button variant="light" size="md" fullWidth iconRight="lightning" className="mt-5">
              Generate allocation
            </Button>
          </CardDark>
        </div>
      </div>
    </DashboardShell>
  );
}

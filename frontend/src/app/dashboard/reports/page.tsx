/**
 * Reports module — exports, insights, and downloads.
 *
 * Reads `getReportExports` and surfaces a one-click download
 * flow that pipes `downloadReportExport`'s blob into a
 * temporary anchor. The "New export" composer posts a job
 * to `createReportExport`.
 */
"use client";

import { useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { Icon, type IconName } from "@/components/ui/icon";
import { ProgressBar, Sparkline } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  createReportExport,
  downloadReportExport,
  getActiveExamPeriod,
  getReportExports,
  type ExamPeriod,
  type Paginated,
  type ReportExport,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

const formatTone: Record<ReportExport["format"], string> = {
  pdf: "bg-rose-50 text-rose-700 ring-rose-200",
  excel: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  csv: "bg-amber-50 text-amber-700 ring-amber-200",
};

const audienceTone: Record<ReportExport["audience"], "neutral" | "brand" | "success" | "warning"> = {
  internal: "neutral",
  registrar: "brand",
  senate: "success",
  public: "warning",
};

const formatIcon: Record<ReportExport["format"], IconName> = {
  pdf: "document",
  excel: "document",
  csv: "document",
};

function fmtSize(bytes: number): string {
  if (bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function extensionFor(format: ReportExport["format"]): string {
  return format === "excel" ? "xlsx" : format;
}

export default function ReportsPage() {
  const [creating, setCreating] = useState(false);
  const [draftFormat, setDraftFormat] = useState<ReportExport["format"]>("pdf");
  const [draftAudience, setDraftAudience] = useState<ReportExport["audience"]>("internal");
  const [draftTitle, setDraftTitle] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const { data, isLoading, error, refresh } = useFetch<{
    exports: Paginated<ReportExport> | null;
    period: ExamPeriod | null;
  }>(async () => {
    const [exports, period] = await Promise.all([
      getReportExports({ page: 1, page_size: 25 }).catch(() => null),
      getActiveExamPeriod().catch(() => null),
    ]);
    return { exports, period };
  }, []);

  const exports = data?.exports?.results ?? [];
  const total = data?.exports?.count ?? 0;

  async function handleDownload(exp: ReportExport) {
    if (!exp.download_url) {
      setActionError("This export has no file attached yet.");
      return;
    }
    setDownloadingId(exp.id);
    setActionError(null);
    try {
      const blob = await downloadReportExport(exp.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${exp.title.replace(/[^a-z0-9-_]+/gi, "_") || "report"}.${extensionFor(exp.format)}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!draftTitle.trim()) return;
    setCreating(true);
    setActionError(null);
    try {
      await createReportExport({
        title: draftTitle.trim(),
        format: draftFormat,
        audience: draftAudience,
        cycle_id: data?.period?.id,
      });
      setDraftTitle("");
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  return (
    <DashboardShell
      title="Reports"
      subtitle="Exports · Insights · Audit"
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
      {error || actionError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Reports error">
            {actionError ?? error?.message}
          </StatusBanner>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Exports total", value: total ? String(total) : isLoading ? "…" : "0", delta: "all-time" },
          {
            label: "PDF exports",
            value: String(exports.filter((e) => e.format === "pdf").length),
            delta: "regulator-ready",
          },
          {
            label: "Excel exports",
            value: String(exports.filter((e) => e.format === "excel").length),
            delta: "for analysis",
          },
          {
            label: "Latest export",
            value: exports[0] ? fmtTime(exports[0].generated_at) : "—",
            delta: exports[0]?.title ?? "no exports yet",
          },
        ].map((i) => (
          <div
            key={i.label}
            className="rounded-3xl bg-surface p-5 ring-1 ring-ink-200 shadow-[var(--shadow-card)]"
          >
            <p className="text-sm text-ink-500">{i.label}</p>
            <p className="mt-2 text-2xl font-semibold tnum text-ink-900">{i.value}</p>
            <p className="mt-1 text-xs text-ink-500">{i.delta}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <Card padded={false}>
          <div className="flex items-center justify-between border-b border-ink-100 p-5">
            <CardHeader
              eyebrow="Library"
              title="Recent exports"
              subtitle="Generated automatically by the cycle close-out job, or on-demand."
            />
          </div>

          {/* Composer */}
          <form
            onSubmit={handleCreate}
            className="grid grid-cols-[1fr_auto_auto_auto] items-end gap-2 border-b border-ink-100 p-5"
          >
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                New export
              </span>
              <input
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                placeholder="e.g. Daily attendance summary"
                className="mt-1 w-full rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 placeholder:text-ink-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              />
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Format
              </span>
              <select
                value={draftFormat}
                onChange={(e) => setDraftFormat(e.target.value as ReportExport["format"])}
                className="mt-1 rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              >
                <option value="pdf">PDF</option>
                <option value="excel">Excel</option>
                <option value="csv">CSV</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
                Audience
              </span>
              <select
                value={draftAudience}
                onChange={(e) => setDraftAudience(e.target.value as ReportExport["audience"])}
                className="mt-1 rounded-xl border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              >
                <option value="internal">Internal</option>
                <option value="registrar">Registrar</option>
                <option value="senate">Senate</option>
                <option value="public">Public</option>
              </select>
            </label>
            <Button variant="primary" size="md" iconLeft="plus" disabled={creating || !draftTitle.trim()} type="submit">
              {creating ? "Creating…" : "Create"}
            </Button>
          </form>

          {exports.length === 0 ? (
            <div className="p-10 text-center text-sm text-ink-500">
              {isLoading ? "Loading exports…" : "No exports yet. Use the form above to generate one."}
            </div>
          ) : (
            <ul className="divide-y divide-ink-100">
              {exports.map((e) => (
                <li
                  key={e.id}
                  className="flex items-center gap-4 px-5 py-4 transition hover:bg-brand-50/30"
                >
                  <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100">
                    <Icon name={formatIcon[e.format]} className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-ink-900">{e.title}</p>
                    <p className="mt-0.5 text-xs text-ink-500">
                      {fmtSize(e.size_bytes)} · {fmtTime(e.generated_at)} · by {e.generated_by_email ?? "system"}
                    </p>
                  </div>
                  <Badge tone={audienceTone[e.audience]}>{e.audience}</Badge>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${formatTone[e.format]}`}>
                    {e.format === "excel" ? "Excel" : e.format.toUpperCase()}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    iconLeft="download"
                    disabled={!e.download_url || downloadingId === e.id}
                    onClick={() => void handleDownload(e)}
                  >
                    {downloadingId === e.id ? "Downloading…" : "Download"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-6">
          <CardDark>
            <p className="eyebrow text-brand-300">Operational insights</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">
              Track what matters this cycle
            </h3>
            <p className="mt-2 text-sm text-brand-100/80">
              Attendance, staffing balance, room usage, and incident trends
              across the current examination period.
            </p>
            <div className="mt-5 grid grid-cols-2 gap-3">
              {[
                { label: "PDF", value: String(exports.filter((e) => e.format === "pdf").length) },
                { label: "Excel", value: String(exports.filter((e) => e.format === "excel").length) },
                { label: "CSV", value: String(exports.filter((e) => e.format === "csv").length) },
                { label: "Total", value: String(exports.length) },
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
            <CardHeader eyebrow="Trend" title="Activity, last 12 weeks" />
            <div className="mt-5">
              <Sparkline
                values={[88, 90, 89, 91, 92, 91, 93, 94, 93, 95, 94, 96]}
                tone="success"
                width={300}
                height={64}
              />
            </div>
            <div className="mt-4">
              <ProgressBar value={94} tone="success" />
            </div>
            <p className="mt-2 text-xs text-ink-500">Cycle target: 95%</p>
          </Card>
        </div>
      </div>
    </DashboardShell>
  );
}

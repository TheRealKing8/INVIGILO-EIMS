import { DashboardShell } from "@/components/dashboard-shell";

const reports = [
  { title: "Daily attendance summary", type: "PDF", updated: "2h ago" },
  { title: "Room utilization report", type: "Excel", updated: "Today" },
  { title: "Incident log", type: "CSV", updated: "Yesterday" },
];

export default function ReportsPage() {
  return (
    <DashboardShell title="Reports">
      <div className="grid gap-6 lg:grid-cols-[1fr_0.8fr]">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-slate-950">Recent exports</h2>
          <div className="mt-6 space-y-3">
            {reports.map((report) => (
              <div key={report.title} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="font-semibold text-slate-900">{report.title}</p>
                  <p className="text-sm text-slate-500">Updated {report.updated}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                  {report.type}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-sky-700">Analytics</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-950">Operational insights</h2>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            Track attendance, staffing balance, room usage, and incident trends across the examination cycle.
          </p>
          <div className="mt-6 rounded-2xl bg-slate-50 p-4">
            <p className="text-3xl font-semibold text-slate-950">94%</p>
            <p className="mt-1 text-sm text-slate-500">Attendance completion rate</p>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}

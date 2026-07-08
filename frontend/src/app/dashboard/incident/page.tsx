import { DashboardShell } from "@/components/dashboard-shell";

const incidentFeed = [
  { title: "Late arrival", severity: "Medium", time: "08:12" },
  { title: "Room equipment issue", severity: "High", time: "09:45" },
  { title: "Student misconduct report", severity: "High", time: "11:20" },
];

export default function IncidentPage() {
  return (
    <DashboardShell title="Incidents">
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-slate-950">Live incident feed</h2>
          <div className="mt-6 space-y-3">
            {incidentFeed.map((item) => (
              <div key={item.title} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="font-semibold text-slate-900">{item.title}</p>
                  <p className="text-sm text-slate-500">Logged at {item.time}</p>
                </div>
                <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-700">
                  {item.severity}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-emerald-700">Response status</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-950">Escalation workflow</h2>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            Incident handling is visible to supervisors, chief invigilators, and examination officers in one place.
          </p>
          <div className="mt-6 space-y-3">
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-semibold text-slate-900">2 urgent cases</p>
              <p className="mt-1 text-sm text-slate-500">Awaiting supervisor acknowledgement.</p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="font-semibold text-slate-900">4 resolved</p>
              <p className="mt-1 text-sm text-slate-500">Filed and archived within the session timeline.</p>
            </div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}

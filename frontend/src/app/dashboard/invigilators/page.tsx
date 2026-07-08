import { DashboardShell } from "@/components/dashboard-shell";

const invigilators = [
  { name: "Alicia Mugo", role: "Senior Invigilator", availability: "Available" },
  { name: "Daniel Otieno", role: "Exam Officer", availability: "Busy" },
  { name: "Grace Wanjiku", role: "Invigilator", availability: "Available" },
];

export default function InvigilatorsPage() {
  return (
    <DashboardShell title="Invigilators">
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-slate-950">Staff roster</h2>
          <div className="mt-6 space-y-3">
            {invigilators.map((person) => (
              <div key={person.name} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="font-semibold text-slate-900">{person.name}</p>
                  <p className="text-sm text-slate-500">{person.role}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                  {person.availability}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <p className="text-sm uppercase tracking-[0.2em] text-slate-400">Allocation</p>
          <h2 className="mt-2 text-2xl font-semibold">Auto-assignment is ready</h2>
          <p className="mt-3 text-sm leading-7 text-slate-300">
            Use workload, availability, and room coverage to assign staff fairly across sessions.
          </p>
          <button className="mt-6 rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-slate-100">
            Generate allocation
          </button>
        </div>
      </div>
    </DashboardShell>
  );
}

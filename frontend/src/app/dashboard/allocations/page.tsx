import { DashboardShell } from "@/components/dashboard-shell";

const allocationRows = [
  { exam: "CS101 Midterm", invigilator: "Alicia Mugo", room: "A3", status: "Confirmed" },
  { exam: "ENG202 Finals", invigilator: "Daniel Otieno", room: "B1", status: "Pending" },
  { exam: "MTH120 Quiz", invigilator: "Grace Wanjiku", room: "C2", status: "Ready" },
];

export default function AllocationsPage() {
  return (
    <DashboardShell title="Allocations">
      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Allocation overview</h2>
              <p className="mt-1 text-sm text-slate-500">Assignment coverage across the active examination period.</p>
            </div>
            <button className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800">
              Optimize
            </button>
          </div>

          <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 font-semibold text-slate-700">Exam</th>
                  <th className="px-4 py-3 font-semibold text-slate-700">Invigilator</th>
                  <th className="px-4 py-3 font-semibold text-slate-700">Room</th>
                  <th className="px-4 py-3 font-semibold text-slate-700">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {allocationRows.map((row) => (
                  <tr key={row.exam}>
                    <td className="px-4 py-3 font-medium text-slate-900">{row.exam}</td>
                    <td className="px-4 py-3 text-slate-600">{row.invigilator}</td>
                    <td className="px-4 py-3 text-slate-600">{row.room}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <p className="text-sm uppercase tracking-[0.24em] text-slate-400">Conflict detection</p>
          <h2 className="mt-2 text-2xl font-semibold">No critical conflicts detected</h2>
          <p className="mt-3 text-sm leading-7 text-slate-300">
            Workload balance and room availability are aligned across the current timetable.
          </p>
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/10 p-4">
            <p className="text-3xl font-semibold">97%</p>
            <p className="mt-1 text-sm text-slate-300">Coverage confidence</p>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}

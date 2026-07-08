import { DashboardShell } from "@/components/dashboard-shell";

const exams = [
  { code: "CS101", title: "Programming Midterm", date: "2026-07-08", room: "A3", status: "Scheduled" },
  { code: "ENG202", title: "Literature Finals", date: "2026-07-09", room: "B1", status: "Ready" },
  { code: "MTH120", title: "Calculus Quiz", date: "2026-07-10", room: "C2", status: "Pending" },
];

export default function ExamsPage() {
  return (
    <DashboardShell title="Examinations">
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-950">Upcoming exams</h2>
            <p className="mt-1 text-sm text-slate-500">Manage schedules, rooms, and session status.</p>
          </div>
          <button className="rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800">
            New exam
          </button>
        </div>

        <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 font-semibold text-slate-700">Code</th>
                <th className="px-4 py-3 font-semibold text-slate-700">Title</th>
                <th className="px-4 py-3 font-semibold text-slate-700">Date</th>
                <th className="px-4 py-3 font-semibold text-slate-700">Room</th>
                <th className="px-4 py-3 font-semibold text-slate-700">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {exams.map((exam) => (
                <tr key={exam.code}>
                  <td className="px-4 py-3 font-medium text-slate-900">{exam.code}</td>
                  <td className="px-4 py-3 text-slate-600">{exam.title}</td>
                  <td className="px-4 py-3 text-slate-600">{exam.date}</td>
                  <td className="px-4 py-3 text-slate-600">{exam.room}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                      {exam.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardShell>
  );
}

"use client";

import Link from "next/link";
import { DashboardShell } from "@/components/dashboard-shell";

const overviewCards = [
  {
    title: "Today’s sessions",
    value: "14",
    detail: "Across 7 venues",
  },
  {
    title: "Pending checks",
    value: "6",
    detail: "Attendance confirmations",
  },
  {
    title: "Incident reports",
    value: "2",
    detail: "Escalation needed",
  },
];

const scheduleItems = [
  { time: "08:00", exam: "CS101 Midterm", room: "Room A3", status: "On track" },
  { time: "10:30", exam: "ENG202 Finals", room: "Room B1", status: "Ready" },
  { time: "13:00", exam: "MTH120 Quiz", room: "Room C2", status: "Pending staff" },
];

export default function DashboardPage() {
  return (
    <DashboardShell
      title="Operations dashboard"
      actions={
        <Link
          href="/login"
          className="inline-flex items-center justify-center rounded-full bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Admin login
        </Link>
      }
    >
      <div className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
        <span className="font-semibold text-slate-900">Your workspace is ready.</span>
        <span className="ml-2">· Review operations, staffing, and incident flow from one place.</span>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {overviewCards.map((card) => (
          <div key={card.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-slate-500">{card.title}</p>
            <p className="mt-3 text-3xl font-semibold text-slate-950">{card.value}</p>
            <p className="mt-2 text-sm text-slate-600">{card.detail}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Today’s schedule</h2>
              <p className="mt-1 text-sm text-slate-500">Live view of the day&apos;s examination flow.</p>
            </div>
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-700">
              Healthy
            </span>
          </div>

          <div className="mt-6 space-y-3">
            {scheduleItems.map((item) => (
              <div key={item.time} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="font-semibold text-slate-900">{item.exam}</p>
                  <p className="text-sm text-slate-500">{item.room}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-slate-900">{item.time}</p>
                  <p className="text-sm text-slate-500">{item.status}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
          <p className="text-sm uppercase tracking-[0.2em] text-slate-400">Alerts</p>
          <h2 className="mt-2 text-2xl font-semibold">A few things need attention</h2>
          <ul className="mt-6 space-y-3 text-sm text-slate-300">
            <li className="rounded-2xl border border-white/10 bg-white/10 p-3">Two invigilators are due for check-in.</li>
            <li className="rounded-2xl border border-white/10 bg-white/10 p-3">One room requires a capacity review.</li>
            <li className="rounded-2xl border border-white/10 bg-white/10 p-3">Daily attendance export is ready to share.</li>
          </ul>
        </section>
      </div>
    </DashboardShell>
  );
}

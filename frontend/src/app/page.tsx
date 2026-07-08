const stats = [
  { label: "Live examinations", value: "120+" },
  { label: "Invigilators assigned", value: "450" },
  { label: "Rooms monitored", value: "85" },
];

const features = [
  {
    title: "Command center",
    description: "Monitor live exam activity across campuses with a real-time operational overview.",
  },
  {
    title: "Allocation intelligence",
    description: "Balance workload, detect conflicts, and assign staff with precision.",
  },
  {
    title: "Audit-ready reporting",
    description: "Export compliance-grade reports for faculties, registrars, and internal review.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[linear-gradient(135deg,_#f8fbff_0%,_#eef4ff_100%)] text-slate-900">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 sm:px-10 lg:px-12">
        <a href="/" className="text-lg font-semibold text-slate-950">INVIGILO</a>
        <nav className="flex items-center gap-2">
          <a href="/" className="rounded-full px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-white">Home</a>
          <a href="/login" className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800">Login</a>
          <a href="/register" className="rounded-full border border-slate-300 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-white">Register</a>
        </nav>
      </header>
      <section className="mx-auto flex max-w-7xl flex-col px-6 py-20 sm:px-10 lg:px-12 lg:py-28">
        <div className="grid items-center gap-10 lg:grid-cols-[1.08fr_0.92fr]">
          <div className="max-w-2xl">
            <span className="inline-flex rounded-full border border-emerald-200 bg-white/80 px-3 py-1 text-sm font-semibold text-emerald-700 shadow-sm">
              INVIGILO · Smart examination invigilation system
            </span>
            <h1 className="mt-6 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl lg:text-6xl">
              A smarter way to run university examinations.
            </h1>
            <p className="mt-5 text-lg leading-8 text-slate-600 sm:text-xl">
              INVIGILO brings scheduling, live monitoring, invigilator allocation, attendance, incidents, and reporting into one secure platform for modern academic institutions.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <a href="/login" className="inline-flex items-center justify-center rounded-full bg-emerald-700 px-6 py-3 text-sm font-semibold text-white transition hover:bg-emerald-800">
                Open the platform
              </a>
              <a href="#features" className="inline-flex items-center justify-center rounded-full border border-slate-300 bg-white/80 px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-white">
                Explore capabilities
              </a>
            </div>
          </div>

          <div className="rounded-[28px] border border-slate-200 bg-slate-950 p-6 text-white shadow-[0_20px_80px_-24px_rgba(15,23,42,0.5)]">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-400">Live status</p>
                <h2 className="mt-2 text-2xl font-semibold">Examination control room</h2>
              </div>
              <span className="rounded-full bg-emerald-500/15 px-3 py-1 text-sm font-semibold text-emerald-300">
                Connected
              </span>
            </div>
            <div className="mt-6 grid gap-4 sm:grid-cols-3">
              {stats.map((item) => (
                <div key={item.label} className="rounded-2xl border border-white/10 bg-white/10 p-4">
                  <p className="text-2xl font-semibold">{item.value}</p>
                  <p className="mt-1 text-sm text-slate-300">{item.label}</p>
                </div>
              ))}
            </div>
            <div className="mt-6 rounded-2xl border border-white/10 bg-white/10 p-4">
              <p className="text-sm font-medium text-slate-300">Next milestone</p>
              <p className="mt-2 text-lg font-semibold">Room readiness verified for 97% of scheduled exams</p>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="border-t border-slate-200/80 bg-white/70 px-6 py-16 backdrop-blur sm:px-10 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-emerald-700">Operational excellence</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              Purpose-built for examination offices, not generic admin tools.
            </h2>
          </div>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {features.map((feature) => (
              <article key={feature.title} className="rounded-3xl border border-slate-200 bg-slate-50 p-6 shadow-sm">
                <h3 className="text-xl font-semibold text-slate-900">{feature.title}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-600">{feature.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

/**
 * INVIGILO marketing landing page.
 *
 * Sections, in order:
 *   1. Hero             — value prop + dark control-room panel
 *   2. Logo strip       — institutional credibility
 *   3. Capabilities     — three feature cards
 *   4. Allocation rules — how the engine works (the 1-50/51-100/etc. table)
 *   5. Workflow         — three steps the office follows
 *   6. CTA              — close the loop
 *
 * Hero CTAs target /login and /register; everything else routes to
 * /dashboard once a user is signed in.
 */
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { BrandLockup } from "@/components/ui/brand";
import { Card, CardDark } from "@/components/ui/card";
import { Icon, type IconName } from "@/components/ui/icon";
import { LogoStrip } from "@/components/ui/logo-strip";
import { MiniBar, ProgressBar, Sparkline } from "@/components/ui/viz";

const heroStats = [
  { label: "Live sessions", value: "12" },
  { label: "Invigilators active", value: "47" },
  { label: "Coverage", value: "98.4%" },
];

const featureCards: { icon: IconName; title: string; body: string }[] = [
  {
    icon: "lightning",
    title: "Smart allocation engine",
    body: "A deterministic rules engine assigns invigilators based on workload, availability, room capacity, and department preference — never on guesswork.",
  },
  {
    icon: "shield",
    title: "Audit-ready by design",
    body: "Every schedule change, check-in, and incident is logged immutably. Export a period report for the registrar in two clicks.",
  },
  {
    icon: "users",
    title: "Role-aware for everyone",
    body: "Administrators, exam officers, heads of department, faculty deans, and invigilators each get a workspace tuned to their responsibilities.",
  },
];

const allocationRules = [
  { capacity: "1 – 50",   invigilators: 1, fill: 0.25 },
  { capacity: "51 – 100", invigilators: 2, fill: 0.5  },
  { capacity: "101 – 150",invigilators: 3, fill: 0.75 },
  { capacity: "151 +",    invigilators: 4, fill: 1.0  },
];

const workflow = [
  {
    n: "01",
    title: "Configure the cycle",
    body: "Add faculties, departments, rooms, and invigilator rosters. INVIGILO comes with sensible defaults for the new semester.",
  },
  {
    n: "02",
    title: "Run the allocation engine",
    body: "Pick an exam period and INVIGILO builds a fair, conflict-free allocation. Review and override per session if needed.",
  },
  {
    n: "03",
    title: "Operate, audit, report",
    body: "Invigilators check in, officers log incidents, the dashboard surfaces what needs attention. Period reports export in PDF, Excel, or CSV.",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-background text-ink-900">
      {/* HEADER --------------------------------------------------------- */}
      <header className="border-b border-ink-200/70 bg-surface/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5 sm:px-10 lg:px-12">
          <BrandLockup size="md" variant="dark" href="/" iconName="shield" />
          <nav className="hidden items-center gap-1 md:flex">
            {[
              { label: "Platform", href: "#capabilities" },
              { label: "Allocation", href: "#engine" },
              { label: "Workflow", href: "#workflow" },
            ].map((it) => (
              <a
                key={it.href}
                href={it.href}
                className="rounded-full px-4 py-2 text-sm font-semibold text-ink-700 transition hover:bg-ink-100"
              >
                {it.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="hidden rounded-full px-4 py-2 text-sm font-semibold text-ink-700 transition hover:bg-ink-100 sm:inline-flex"
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-brand-700 px-5 text-sm font-semibold text-white shadow-sm shadow-brand-900/20 transition hover:bg-brand-800"
            >
              Request access
              <Icon name="arrow-right" className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* HERO ----------------------------------------------------------- */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-x-0 -top-32 h-[420px] bg-[radial-gradient(ellipse_at_top,_var(--brand-200)_0%,_transparent_60%)] opacity-60"
          aria-hidden
        />
        <div className="relative mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-12 lg:py-28">
          <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr]">
            <div>
              <Badge tone="brand" className="px-3 py-1 text-xs">
                <Icon name="sparkle" className="h-3 w-3" />
                Smart examination invigilation
              </Badge>
              <h1 className="display mt-6 text-4xl text-ink-900 sm:text-5xl lg:text-6xl">
                The control room for your university's examinations.
              </h1>
              <p className="mt-5 max-w-xl text-lg leading-8 text-ink-500">
                INVIGILO brings scheduling, live monitoring, invigilator
                allocation, attendance, incidents, and reporting into one
                secure platform — built for the realities of academic
                operations.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/login"
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-brand-700 px-6 text-base font-semibold text-white shadow-sm shadow-brand-900/20 transition hover:bg-brand-800"
                >
                  Open the platform
                  <Icon name="arrow-right" className="h-4 w-4" />
                </Link>
                <Link
                  href="#capabilities"
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-surface px-6 text-base font-semibold text-ink-900 ring-1 ring-inset ring-ink-200 transition hover:bg-ink-100"
                >
                  Explore capabilities
                </Link>
              </div>

              <div className="mt-10 flex items-center gap-6 text-sm text-ink-500">
                <div className="flex items-center gap-2">
                  <Icon name="check" className="h-4 w-4 text-brand-600" />
                  No credit card
                </div>
                <div className="flex items-center gap-2">
                  <Icon name="check" className="h-4 w-4 text-brand-600" />
                  Free for 1 exam cycle
                </div>
                <div className="flex items-center gap-2">
                  <Icon name="check" className="h-4 w-4 text-brand-600" />
                  Self-hosted or cloud
                </div>
              </div>
            </div>

            <CardDark padded={false} className="p-1">
              <div className="rounded-[22px] bg-surface-dark p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="eyebrow text-brand-300">Live status</p>
                    <h2 className="mt-2 text-2xl font-semibold">Examination control room</h2>
                  </div>
                  <Badge tone="success" withDot>
                    All systems operational
                  </Badge>
                </div>

                <div className="mt-6 grid grid-cols-3 gap-3">
                  {heroStats.map((s) => (
                    <div
                      key={s.label}
                      className="rounded-2xl bg-white/[0.04] p-4 ring-1 ring-inset ring-white/10"
                    >
                      <p className="text-2xl font-semibold tnum tracking-tight text-white">{s.value}</p>
                      <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-200/80">
                        {s.label}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="mt-5 rounded-2xl bg-white/[0.04] p-4 ring-1 ring-inset ring-white/10">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-white">Today's allocation</p>
                    <p className="text-xs text-brand-200/70">142 of 144 seats filled</p>
                  </div>
                  <div className="mt-3">
                    <ProgressBar value={98.6} tone="success" />
                  </div>
                  <div className="mt-3 flex items-center justify-between text-[11px] text-brand-200/70">
                    <span>Confidence: 98.6%</span>
                    <span>2 unfilled → auto re-route</span>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl bg-white/[0.04] p-4 ring-1 ring-inset ring-white/10">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-medium text-brand-200/80">Hourly attendance</p>
                      <Icon name="users" className="h-3.5 w-3.5 text-brand-300" />
                    </div>
                    <div className="mt-3">
                      <Sparkline
                        values={[42, 51, 48, 60, 71, 78, 84, 90, 88, 92, 95, 97]}
                        tone="success"
                        width={180}
                        height={36}
                      />
                    </div>
                  </div>
                  <div className="rounded-2xl bg-white/[0.04] p-4 ring-1 ring-inset ring-white/10">
                    <p className="text-xs font-medium text-brand-200/80">By faculty</p>
                    <div className="mt-3">
                      <MiniBar
                        values={[72, 90, 64, 81, 95, 70, 88]}
                        labels={["S", "M", "T", "W", "T", "F", "S"]}
                        tone="brand"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </CardDark>
          </div>
        </div>
      </section>

      {/* LOGO STRIP ----------------------------------------------------- */}
      <section className="border-y border-ink-200 bg-surface/60">
        <div className="mx-auto max-w-7xl px-6 py-8 sm:px-10 lg:px-12">
          <p className="text-center text-xs font-semibold uppercase tracking-[0.18em] text-ink-500">
            Trusted by examination offices at
          </p>
          <div className="mt-6">
            <LogoStrip />
          </div>
        </div>
      </section>

      {/* CAPABILITIES --------------------------------------------------- */}
      <section id="capabilities" className="mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-12 lg:py-24">
        <div className="max-w-2xl">
          <p className="eyebrow text-brand-700">Operational excellence</p>
          <h2 className="display mt-3 text-3xl text-ink-900 sm:text-4xl">
            Purpose-built for examination offices, not generic admin tools.
          </h2>
          <p className="mt-4 text-base leading-7 text-ink-500">
            INVIGILO models the way your team actually runs a cycle —
            periods, sessions, rooms, invigilators, attendance, and
            incidents — and gives every role a workspace tuned to their
            responsibilities.
          </p>
        </div>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {featureCards.map((c) => (
            <Card key={c.title} className="h-full">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100">
                <Icon name={c.icon} className="h-5 w-5" />
              </div>
              <h3 className="mt-5 text-lg font-semibold text-ink-900">{c.title}</h3>
              <p className="mt-2 text-sm leading-7 text-ink-500">{c.body}</p>
              <div className="mt-5 flex items-center gap-2 text-sm font-semibold text-brand-700">
                Learn more
                <Icon name="arrow-right" className="h-3.5 w-3.5" />
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* ALLOCATION ENGINE --------------------------------------------- */}
      <section id="engine" className="bg-surface">
        <div className="mx-auto grid max-w-7xl items-stretch gap-10 px-6 py-20 sm:px-10 lg:grid-cols-[0.95fr_1.05fr] lg:px-12 lg:py-24">
          <div>
            <p className="eyebrow text-brand-700">Smart allocation engine</p>
            <h2 className="display mt-3 text-3xl text-ink-900 sm:text-4xl">
              Fair, transparent, repeatable — and tunable when it has to be.
            </h2>
            <p className="mt-4 text-base leading-7 text-ink-500">
              INVIGILO follows a deterministic rules table so two exam
              officers running the same input always get the same
              allocation. When something has to be different — a room
              swap, a special-access candidate — every change is logged
              with the operator and the reason.
            </p>
            <ul className="mt-6 space-y-3 text-sm text-ink-700">
              {[
                "Respects invigilator availability and daily allocation caps",
                "Honours department preference and room capacity rules",
                "Surfaces conflicts (room double-booking, staff overlap) before they happen",
                "One-click re-run after a manual override",
              ].map((it) => (
                <li key={it} className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100">
                    <Icon name="check" className="h-3 w-3" />
                  </span>
                  {it}
                </li>
              ))}
            </ul>
          </div>

          <Card padded={false} className="overflow-hidden">
            <div className="border-b border-ink-100 bg-ink-100/40 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="eyebrow text-brand-700">Rule table</p>
                  <h3 className="mt-1 text-lg font-semibold text-ink-900">
                    Room capacity → invigilators
                  </h3>
                </div>
                <Badge tone="brand" withDot>Live</Badge>
              </div>
            </div>
            <div className="divide-y divide-ink-100">
              {allocationRules.map((r) => (
                <div key={r.capacity} className="grid grid-cols-[1fr_1fr_2fr] items-center gap-6 px-5 py-4">
                  <div>
                    <p className="text-sm font-semibold text-ink-900">{r.capacity}</p>
                    <p className="text-xs text-ink-500">candidates</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-2xl font-semibold tnum text-brand-700">
                      {r.invigilators}
                    </span>
                    <span className="text-xs text-ink-500">invigilators</span>
                  </div>
                  <ProgressBar value={r.fill * 100} tone="brand" />
                </div>
              ))}
            </div>
            <div className="bg-ink-100/30 p-5 text-xs text-ink-500">
              Default rule. Departments can submit overrides for special
              populations (candidates with disabilities, multi-language
              papers) and the engine will apply them.
            </div>
          </Card>
        </div>
      </section>

      {/* WORKFLOW ------------------------------------------------------ */}
      <section id="workflow" className="mx-auto max-w-7xl px-6 py-20 sm:px-10 lg:px-12 lg:py-24">
        <div className="max-w-2xl">
          <p className="eyebrow text-brand-700">How a cycle runs</p>
          <h2 className="display mt-3 text-3xl text-ink-900 sm:text-4xl">
            From setup to sign-off in three moves.
          </h2>
        </div>
        <ol className="mt-10 grid gap-6 md:grid-cols-3">
          {workflow.map((w) => (
            <Card key={w.n} className="h-full">
              <span className="text-5xl font-semibold tnum text-brand-200">{w.n}</span>
              <h3 className="mt-3 text-lg font-semibold text-ink-900">{w.title}</h3>
              <p className="mt-2 text-sm leading-7 text-ink-500">{w.body}</p>
            </Card>
          ))}
        </ol>
      </section>

      {/* CTA ----------------------------------------------------------- */}
      <section className="mx-auto max-w-7xl px-6 pb-20 sm:px-10 lg:px-12">
        <CardDark>
          <div className="grid items-center gap-8 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <p className="eyebrow text-brand-300">Run your next cycle</p>
              <h2 className="display mt-3 text-3xl text-white sm:text-4xl">
                See what the operations team sees, on day one.
              </h2>
              <p className="mt-4 max-w-xl text-base leading-7 text-brand-100/80">
                Spin up a workspace for one exam cycle, free. We'll import a
                sample timetable and roster so you can click through the
                experience in under five minutes.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row lg:justify-end">
              <Link
                href="/register"
                className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-surface px-6 text-base font-semibold text-brand-700 shadow-sm transition hover:bg-ink-100"
              >
                Request officer access
                <Icon name="arrow-right" className="h-4 w-4" />
              </Link>
              <Link
                href="/login"
                className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-white/5 px-6 text-base font-semibold text-white ring-1 ring-inset ring-white/15 transition hover:bg-white/10"
              >
                Sign in
              </Link>
            </div>
          </div>
        </CardDark>
      </section>

      {/* FOOTER -------------------------------------------------------- */}
      <footer className="border-t border-ink-200 bg-surface/60">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-4 px-6 py-8 sm:flex-row sm:items-center sm:px-10 lg:px-12">
          <BrandLockup size="sm" variant="dark" showSubtitle={false} />
          <p className="text-xs text-ink-500">
            INVIGILO © 2026 · Examination operations for modern universities
          </p>
        </div>
      </footer>
    </div>
  );
}

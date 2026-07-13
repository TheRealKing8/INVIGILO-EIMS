/**
 * AuthShell — the frame every auth page sits inside.
 *
 * Two-column layout on desktop:
 *
 *   ┌──────────────────────┬──────────────────────┐
 *   │ Brand / hero panel   │ Form / status panel  │
 *   │ (emerald-950)        │ (white)              │
 *   └──────────────────────┴──────────────────────┘
 *
 * The hero panel doubles as a "what is this product" pitch on public
 * pages and a compact system status on sign-in.
 */
import Link from "next/link";
import { type ReactNode } from "react";
import { BrandLockup } from "@/components/ui/brand";
import { Icon, type IconName } from "@/components/ui/icon";

type AuthShellProps = {
  title: string;
  subtitle: string;
  children: ReactNode;
  /** Optional link rendered in the top-right of the form panel. */
  altLink?: { href: string; label: string };
  /** What to show in the dark side panel. */
  hero?: {
    eyebrow?: string;
    headline: string;
    bullets?: { icon: IconName; title: string; detail: string }[];
    stats?: { label: string; value: string }[];
  };
  /** Optional footer line (e.g. a license line). */
  footerNote?: string;
};

const defaultBullets: { icon: IconName; title: string; detail: string }[] = [
  {
    icon: "shield",
    title: "Audit-ready by default",
    detail: "Every allocation, check-in, and incident is logged immutably.",
  },
  {
    icon: "lightning",
    title: "Allocation in seconds",
    detail: "Deterministic rules engine balances invigilator workload.",
  },
  {
    icon: "users",
    title: "Role-aware for everyone",
    detail: "Admins, officers, HODs, deans, and invigilators — one workspace.",
  },
];

export function AuthShell({
  title,
  subtitle,
  children,
  altLink,
  hero,
  footerNote = "INVIGILO © 2026 · Examination operations for modern universities",
}: AuthShellProps) {
  const heroBullets = hero?.bullets ?? defaultBullets;
  const heroStats = hero?.stats ?? [
    { label: "Exams this week", value: "184" },
    { label: "Invigilators assigned", value: "612" },
    { label: "Coverage confidence", value: "98.4%" },
  ];

  return (
    <div className="min-h-screen bg-background text-ink-900">
      <header className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-6 sm:px-10 lg:px-12">
        <BrandLockup size="md" variant="dark" href="/" iconName="shield" />
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm font-semibold text-ink-900 ring-1 ring-inset ring-ink-200 transition hover:bg-ink-100"
        >
          <Icon name="arrow-right" className="h-3.5 w-3.5 -rotate-180" />
          Home
        </Link>
      </header>

      <main className="flex items-center justify-center px-4 pb-10 pt-2 sm:px-6 lg:px-8">
        <div className="w-full max-w-6xl overflow-hidden rounded-[32px] bg-surface shadow-[var(--shadow-elev)] ring-1 ring-ink-200/70 lg:grid lg:grid-cols-[0.95fr_1.05fr]">
          {/* HERO PANEL — emerald-950 ---------------------------------------- */}
          <aside className="relative hidden overflow-hidden bg-surface-dark p-10 text-white lg:flex lg:flex-col">
            <div className="dot-bg absolute inset-0 opacity-60" aria-hidden />
            <div
              className="absolute -right-32 -top-32 h-72 w-72 rounded-full bg-brand-500/30 blur-3xl"
              aria-hidden
            />
            <div
              className="absolute -bottom-40 -left-20 h-80 w-80 rounded-full bg-brand-700/40 blur-3xl"
              aria-hidden
            />

            <div className="relative">
              <p className="eyebrow text-brand-300">
                {hero?.eyebrow ?? "Secure access"}
              </p>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                {hero?.headline ?? title}
              </h1>
              <p className="mt-4 max-w-md text-sm leading-7 text-brand-100/80">
                {subtitle}
              </p>
            </div>

            <ul className="relative mt-10 space-y-3">
              {heroBullets.map((b) => (
                <li
                  key={b.title}
                  className="flex items-start gap-3 rounded-2xl bg-white/[0.04] p-4 ring-1 ring-inset ring-white/10"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300 ring-1 ring-inset ring-brand-500/30">
                    <Icon name={b.icon} className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{b.title}</p>
                    <p className="mt-0.5 text-xs text-brand-100/70">{b.detail}</p>
                  </div>
                </li>
              ))}
            </ul>

            <div className="relative mt-10 grid grid-cols-3 gap-3">
              {heroStats.map((s) => (
                <div
                  key={s.label}
                  className="rounded-2xl bg-white/[0.04] p-4 ring-1 ring-inset ring-white/10"
                >
                  <p className="text-2xl font-semibold tnum tracking-tight text-white">
                    {s.value}
                  </p>
                  <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.16em] text-brand-200/80">
                    {s.label}
                  </p>
                </div>
              ))}
            </div>
          </aside>

          {/* FORM PANEL — white -------------------------------------------- */}
          <section className="bg-surface p-8 sm:p-10 lg:p-12">
            <div className="mx-auto w-full max-w-md">
              <div className="lg:hidden">
                <BrandLockup size="md" variant="dark" href="/" iconName="shield" />
              </div>
              <div className="mt-6 lg:mt-0">
                <h2 className="display text-2xl font-semibold text-ink-900">
                  {title}
                </h2>
                <p className="mt-2 text-sm text-ink-500">{subtitle}</p>
              </div>
              <div className="mt-8">{children}</div>

              {altLink ? (
                <p className="mt-6 text-sm text-ink-500">
                  {altLink.href === "/login" ? "New to Invigilo?" : "Already on Invigilo?"}{" "}
                  <Link
                    href={altLink.href}
                    className="font-semibold text-brand-700 transition hover:text-brand-800"
                  >
                    {altLink.label}
                  </Link>
                </p>
              ) : null}
            </div>
          </section>
        </div>
      </main>

      <footer className="border-t border-ink-200/70 bg-surface/60 px-6 py-5 text-center text-xs text-ink-500 backdrop-blur sm:px-10 lg:px-12">
        {footerNote}
      </footer>
    </div>
  );
}

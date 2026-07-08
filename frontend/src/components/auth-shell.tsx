import Link from "next/link";
import type { ReactNode } from "react";

type AuthShellProps = {
  title: string;
  subtitle: string;
  children: ReactNode;
  footerText?: string;
  footerLink?: { href: string; label: string };
};

export function AuthShell({
  title,
  subtitle,
  children,
  footerText,
  footerLink,
}: AuthShellProps) {
  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,_#f8fbff_0%,_#eef4ff_100%)] text-slate-900">
      <header className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-6 sm:px-10 lg:px-12">
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-700 text-lg font-semibold text-white shadow-lg shadow-emerald-700/20">
            I
          </div>
          <div>
            <p className="text-lg font-semibold text-slate-950">INVIGILO</p>
            <p className="text-sm text-slate-500">Smart examination invigilation</p>
          </div>
        </Link>

        <Link
          href="/"
          className="inline-flex items-center rounded-full border border-slate-300 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-white"
        >
          Home
        </Link>
      </header>

      <main className="flex items-center justify-center px-4 pb-10 pt-4 sm:px-6 lg:px-8">
        <div className="w-full max-w-5xl rounded-[32px] border border-slate-200 bg-white/90 p-4 shadow-[0_20px_80px_-24px_rgba(15,23,42,0.35)] backdrop-blur sm:p-8 lg:grid lg:grid-cols-[0.95fr_1.05fr] lg:gap-8 lg:p-10">
          <div className="rounded-[24px] bg-slate-950 p-8 text-white">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-emerald-300">Secure access</p>
            <h1 className="mt-4 text-3xl font-semibold sm:text-4xl">{title}</h1>
            <p className="mt-4 text-sm leading-7 text-slate-300">{subtitle}</p>
            <div className="mt-8 rounded-2xl border border-white/10 bg-white/10 p-4">
              <p className="text-sm font-medium text-slate-300">Operational readiness</p>
              <p className="mt-2 text-2xl font-semibold">97% audit-ready</p>
            </div>
          </div>

          <div className="flex flex-col justify-center px-2 py-6 sm:px-4 lg:px-2 lg:py-0">
            {children}
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-200/80 bg-white/70 px-6 py-6 text-center text-sm text-slate-500 sm:px-10 lg:px-12">
        <p>INVIGILO © 2026 · Examination operations for modern universities</p>
      </footer>
    </div>
  );
}

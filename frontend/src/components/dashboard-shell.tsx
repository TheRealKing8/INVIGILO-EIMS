"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { clearAuthTokens, getProfile, getStoredAccessToken, getStoredUser } from "@/lib/api";

type NavItem = {
  href: string;
  label: string;
  icon: string;
};

const navItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: "◉" },
  { href: "/dashboard/exams", label: "Examinations", icon: "▣" },
  { href: "/dashboard/invigilators", label: "Invigilators", icon: "◎" },
  { href: "/dashboard/reports", label: "Reports", icon: "◌" },
  { href: "/dashboard/allocations", label: "Allocations", icon: "◍" },
  { href: "/dashboard/incident", label: "Incidents", icon: "⚑" },
];

export function DashboardShell({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userName, setUserName] = useState("Operations team");

  useEffect(() => {
    const accessToken = getStoredAccessToken();
    const storedUser = getStoredUser();

    if (!accessToken) {
      clearAuthTokens();
      setIsAuthenticated(false);
      setIsReady(true);
      router.replace("/login");
      return;
    }

    setUserName(storedUser?.full_name || storedUser?.email || "Operations team");

    getProfile(accessToken)
      .then((profile) => {
        setUserName(profile.full_name || profile.email || "Operations team");
        setIsAuthenticated(true);
      })
      .catch(() => {
        clearAuthTokens();
        setIsAuthenticated(false);
        router.replace("/login");
      })
      .finally(() => {
        setIsReady(true);
      });
  }, [router]);

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm font-medium text-slate-600">
        Verifying your session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col lg:flex-row">
        <aside className="w-full border-b border-slate-200 bg-slate-950 px-6 py-6 text-slate-200 lg:w-72 lg:border-b-0 lg:border-r lg:px-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-700 text-lg font-semibold text-white shadow-lg shadow-emerald-700/20">
              I
            </div>
            <div>
              <p className="text-lg font-semibold text-white">INVIGILO</p>
              <p className="text-sm text-slate-400">Smart examination invigilation</p>
            </div>
          </div>

          <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-3 text-sm text-slate-300">
            <p className="font-medium text-white">Live command center</p>
            <p className="mt-1">Signed in as {userName}</p>
            <p className="mt-1">12 sessions active · 94% attendance</p>
          </div>

          <nav className="mt-8 space-y-1.5">
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium transition ${
                    isActive
                      ? "bg-emerald-700 text-white shadow-lg shadow-emerald-700/20"
                      : "text-slate-300 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <span>{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="flex-1 p-6 sm:p-8 lg:p-10">
          <div className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-sm backdrop-blur sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-emerald-700">
                Examination operations center
              </p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
            </div>
            {actions}
          </div>
          <div className="mt-8">{children}</div>
        </main>
      </div>
    </div>
  );
}

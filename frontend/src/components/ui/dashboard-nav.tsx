/**
 * Topbar — the small bar at the top of every authenticated page.
 *
 * Holds (left to right): page title block, a search input, a notifications
 * trigger, and a profile menu. The search input is intentionally a stub:
 * when the API is wired up, it should query `?q=` against the relevant
 * list endpoint. The profile menu signs the user out and clears tokens.
 *
 * The sidebar / mobile drawer render only the nav items the user is
 * allowed to see. The map of route -> allowed roles lives in
 * ``@/lib/route-config`` so the route guards and the nav cannot
 * drift apart.
 */
"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { BrandMark } from "@/components/ui/brand";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { SearchPopover } from "@/components/search-popover";
import type { AuthUser } from "@/lib/api";
import { getUnreadCount } from "@/lib/api";
import { visibleNavItems, type RouteAccess } from "@/lib/route-config";

type NavItem = RouteAccess; // alias to keep the rest of this file unchanged

const initialsOf = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase() || "?";

/**
 * Resolve the visible nav items for a user. The source list comes
 * from ``@/lib/route-config``; the per-role filter is the same one
 * the route guards use.
 */
function navFor(user: AuthUser | null): NavItem[] {
  return visibleNavItems(user?.primary_role ?? user?.role);
}

export function Sidebar({
  pathname,
  user,
  onSignOut,
}: {
  pathname: string;
  user: AuthUser | null;
  onSignOut: () => void;
}) {
  return (
    <aside className="hidden h-screen w-72 shrink-0 flex-col border-r border-ink-900/5 bg-surface-dark text-white lg:flex">
      <div className="flex h-16 items-center px-6">
        <BrandMark size="md" variant="dark" />
        <div className="ml-3 leading-tight">
          <p className="text-sm font-semibold tracking-[0.22em] text-white">INVIGILO</p>
          <p className="text-[11px] font-medium text-brand-200/70">Examination operations</p>
        </div>
      </div>

      <div className="mx-4 mt-2 rounded-2xl border border-white/5 bg-white/[0.04] p-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-sm font-semibold text-white ring-1 ring-inset ring-white/10">
            {initialsOf(user?.full_name || user?.email || "User")}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-white">
              {user?.full_name || user?.email || "Operations team"}
            </p>
            <p className="truncate text-xs text-brand-200/70">
              {user?.primary_role || user?.role || "Operations"}
            </p>
          </div>
          <span
            className="h-2 w-2 rounded-full bg-brand-400 pulse-ring"
            aria-label="Online"
          />
        </div>
      </div>

      <nav className="mt-6 flex-1 overflow-y-auto px-3 pb-4">
        <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-200/60">
          Workspace
        </p>
        <ul className="space-y-1">
          {navFor(user).map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={[
                    "group flex items-start gap-3 rounded-2xl px-3 py-2.5 text-sm transition",
                    isActive
                      ? "bg-brand-700 text-white shadow-[var(--shadow-elev)]"
                      : "text-brand-100/80 hover:bg-white/[0.04] hover:text-white",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl",
                      isActive
                        ? "bg-white/15 text-white"
                        : "bg-white/[0.04] text-brand-200 group-hover:text-white",
                    ].join(" ")}
                  >
                    <Icon name={item.icon} className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{item.label}</span>
                    <span
                      className={[
                        "block truncate text-[11px]",
                        isActive ? "text-brand-100/80" : "text-brand-200/60",
                      ].join(" ")}
                    >
                      {item.description}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.04] p-4">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-300">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-400 pulse-ring" />
            Live status
          </div>
          <p className="mt-2 text-sm font-semibold text-white">All systems operational</p>
          <p className="mt-1 text-xs text-brand-200/70">
            Sync 4s ago · Database · Cache · Email
          </p>
        </div>
      </nav>

      <div className="border-t border-white/5 p-4">
        <button
          onClick={onSignOut}
          className="group flex w-full items-center justify-between rounded-2xl px-3 py-2.5 text-sm font-medium text-brand-100/80 transition hover:bg-white/[0.04] hover:text-white"
        >
          <span className="flex items-center gap-3">
            <Icon name="logout" className="h-4 w-4" />
            Sign out
          </span>
          <Icon name="arrow-right" className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
        </button>
      </div>
    </aside>
  );
}

export function MobileNav({
  pathname,
  user,
  onSignOut,
}: {
  pathname: string;
  user: AuthUser | null;
  onSignOut: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-ink-200 bg-surface lg:hidden">
      <div className="flex h-14 items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <BrandMark size="sm" variant="light" />
          <span className="text-sm font-semibold tracking-[0.22em] text-ink-900">INVIGILO</span>
        </div>
        <button
          onClick={() => setOpen((o) => !o)}
          className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-ink-100 text-ink-700 ring-1 ring-inset ring-ink-200"
          aria-label="Toggle menu"
        >
          <Icon name={open ? "x" : "menu"} className="h-5 w-5" />
        </button>
      </div>
      {open ? (
        <nav className="space-y-1 px-3 pb-3">
          {navFor(user).map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={[
                  "flex items-center gap-3 rounded-2xl px-3 py-2 text-sm font-medium",
                  isActive
                    ? "bg-brand-700 text-white"
                    : "text-ink-700 hover:bg-ink-100",
                ].join(" ")}
              >
                <Icon name={item.icon} className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
          <button
            onClick={onSignOut}
            className="flex w-full items-center gap-3 rounded-2xl px-3 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50"
          >
            <Icon name="logout" className="h-4 w-4" />
            Sign out
          </button>
          <div className="mt-2 flex items-center justify-between rounded-2xl bg-ink-100/60 px-3 py-2 ring-1 ring-inset ring-ink-200">
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-500">
              Theme
            </span>
            <ThemeToggle />
          </div>
        </nav>
      ) : null}
    </div>
  );
}

export function Topbar({
  user,
  onSignOut,
  title,
  subtitle,
  actions,
}: {
  user: AuthUser | null;
  onSignOut: () => void;
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [unread, setUnread] = useState<number | null>(null);
  const router = useRouter();
  const menuRef = useRef<HTMLDivElement | null>(null);
  const searchWrapRef = useRef<HTMLDivElement | null>(null);

  // Poll the unread-count endpoint every 60s. SA + EO don't have the
  // ``notification.view_own`` codename (see apps.accounts.seed), so
  // the bell stays at "— / no badge" for them. The call may 403 in
  // that case — we silently ignore the failure and keep the previous
  // count on screen so the badge never blinks.
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const { count } = await getUnreadCount();
        if (!cancelled) setUnread(count);
      } catch {
        if (!cancelled) setUnread((prev) => prev ?? 0);
      } finally {
        if (!cancelled) timer = setTimeout(tick, 60_000);
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    }
    if (menuOpen) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [menuOpen]);

  // Escape closes the popover, mirrors the menu's UX.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setSearchOpen(false);
        setQuery("");
      }
    }
    if (searchOpen) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [searchOpen]);

  function closeSearch() {
    setSearchOpen(false);
    setQuery("");
  }

  return (
    <header className="sticky top-0 z-30 border-b border-ink-200 bg-surface/80 backdrop-blur">
      <div className="flex flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8 lg:py-5">
        <div className="min-w-0">
          {subtitle ? (
            <p className="eyebrow text-brand-700">{subtitle}</p>
          ) : null}
          <h1 className="display mt-1 text-2xl font-semibold text-ink-900 sm:text-3xl">
            {title}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative hidden md:block" ref={searchWrapRef}>
            <Icon
              name="search"
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
            />
            <input
              id="topbar-search"
              aria-label="Search exams, staff, and rooms"
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => query.length >= 2 && setSearchOpen(true)}
              placeholder="Search exams, staff, rooms…"
              className="h-11 w-72 rounded-full border-0 bg-ink-100/60 pl-10 pr-4 text-sm text-ink-900 placeholder:text-ink-400 ring-1 ring-inset ring-ink-200 transition focus:bg-surface focus:ring-2 focus:ring-brand-500"
            />
            {searchOpen && query.trim().length >= 2 ? (
              <SearchPopover
                query={query}
                onClose={closeSearch}
                containerRef={searchWrapRef}
              />
            ) : null}
          </div>

          <ThemeToggle />

          <button
            onClick={() => router.push("/dashboard/notifications")}
            className="relative inline-flex h-11 w-11 items-center justify-center rounded-full bg-ink-100/60 text-ink-700 ring-1 ring-inset ring-ink-200 transition hover:bg-surface"
            aria-label={
              unread && unread > 0
                ? `Notifications, ${unread} unread`
                : "Notifications"
            }
          >
            <Icon name="bell" className="h-4 w-4" />
            {unread != null && unread > 0 ? (
              <span className="absolute -right-0.5 -top-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white ring-2 ring-white">
                {unread > 99 ? "99+" : unread}
              </span>
            ) : null}
          </button>

          {actions}

          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="inline-flex items-center gap-3 rounded-full bg-ink-100/60 py-1.5 pl-1.5 pr-3 text-sm text-ink-900 ring-1 ring-inset ring-ink-200 transition hover:bg-surface"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white">
                {initialsOf(user?.full_name || user?.email || "User")}
              </span>
              <span className="hidden text-left sm:block">
                <span className="block max-w-[140px] truncate text-sm font-semibold">
                  {user?.full_name || user?.email || "User"}
                </span>
                <span className="block text-[11px] text-ink-500">
                  {user?.primary_role || user?.role || "Operations"}
                </span>
              </span>
              <Icon name="chevron-down" className="h-3.5 w-3.5 text-ink-500" />
            </button>
            {menuOpen ? (
              <div className="absolute right-0 mt-2 w-60 overflow-hidden rounded-2xl bg-surface shadow-[var(--shadow-elev)] ring-1 ring-ink-200">
                <div className="border-b border-ink-100 p-3">
                  <p className="truncate text-sm font-semibold text-ink-900">
                    {user?.full_name || user?.email || "User"}
                  </p>
                  <p className="truncate text-xs text-ink-500">{user?.email}</p>
                  <div className="mt-2">
                    <Badge tone="brand">
                      {user?.primary_role || user?.role || "Operations"}
                    </Badge>
                  </div>
                </div>
                <ul className="p-1 text-sm">
                  <li>
                    <button
                      onClick={() => {
                        setMenuOpen(false);
                        router.push("/dashboard");
                      }}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-ink-700 transition hover:bg-ink-100"
                    >
                      <Icon name="dashboard" className="h-4 w-4" />
                      Overview
                    </button>
                  </li>
                  <li>
                    <button
                      onClick={() => {
                        setMenuOpen(false);
                        onSignOut();
                      }}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-rose-700 transition hover:bg-rose-50"
                    >
                      <Icon name="logout" className="h-4 w-4" />
                      Sign out
                    </button>
                  </li>
                </ul>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}

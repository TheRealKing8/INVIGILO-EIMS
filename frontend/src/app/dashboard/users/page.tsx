/**
 * Users — admin-only user management surface.
 *
 * Lists every account in the system with role/status/last-sign-in
 * summaries. Click a row to open the detail page (password reset,
 * role assignment, disable, unlock).
 *
 * Backend gating: list is gated by ``accounts.user.create``. The
 * detail page's reset-password and set-roles actions are gated by
 * their own narrower codenames (SA only). The nav entry is hidden
 * for non-SA roles by ``route-config.ts``; the route guard catches
 * direct-URL access.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { StatusBanner } from "@/components/ui/status-banner";
import { getUsers, type User } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

// All 8 role codes, in the same display order as the seed module.
const ROLE_OPTIONS = [
  { code: "SYSTEM_ADMINISTRATOR", label: "System Admin" },
  { code: "EXAMINATION_OFFICER", label: "Exam Officer" },
  { code: "FACULTY_DEAN", label: "Faculty Dean" },
  { code: "HEAD_OF_DEPARTMENT", label: "Head of Dept." },
  { code: "INVIGILATOR", label: "Invigilator" },
  { code: "SECURITY_OFFICER", label: "Security Officer" },
  { code: "STUDENT", label: "Student" },
  { code: "GUEST", label: "Guest" },
] as const;

function fmtRelative(iso: string | null): string {
  if (!iso) return "Never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = Date.now() - then;
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "Just now";
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hr ago`;
  const d = Math.floor(hr / 24);
  if (d < 30) return `${d} day${d === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString();
}

function statusOf(user: User): { label: string; tone: "success" | "warning" | "neutral" } {
  if (!user.is_active) return { label: "Disabled", tone: "neutral" };
  if (user.locked_until && new Date(user.locked_until).getTime() > Date.now()) {
    return { label: "Locked", tone: "warning" };
  }
  return { label: "Active", tone: "success" };
}

export default function UsersPage() {
  const router = useRouter();
  const { data, isLoading, error, refresh } = useFetch(() => getUsers(), []);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const allUsers: User[] = useMemo(() => data ?? [], [data]);

  const filtered = useMemo(() => {
    return allUsers.filter((u) => {
      // Role filter — match against any of the user's roles.
      if (roleFilter) {
        if (!u.roles.some((r) => r.code === roleFilter)) return false;
      }
      // Status filter.
      if (statusFilter === "active" && !u.is_active) return false;
      if (statusFilter === "disabled" && u.is_active) return false;
      if (statusFilter === "locked") {
        if (!(u.locked_until && new Date(u.locked_until).getTime() > Date.now())) {
          return false;
        }
      }
      if (statusFilter === "never" && u.last_login_at) return false;
      // Search — full name + email (client-side only).
      if (search) {
        const q = search.toLowerCase();
        if (
          !u.email.toLowerCase().includes(q) &&
          !(u.full_name || "").toLowerCase().includes(q)
        ) {
          return false;
        }
      }
      return true;
    });
  }, [allUsers, search, roleFilter, statusFilter]);

  const kpis = useMemo(() => {
    const total = allUsers.length;
    const active = allUsers.filter((u) => u.is_active).length;
    const locked = allUsers.filter(
      (u) => u.locked_until && new Date(u.locked_until).getTime() > Date.now(),
    ).length;
    const neverSignedIn = allUsers.filter((u) => !u.last_login_at).length;
    return { total, active, locked, neverSignedIn };
  }, [allUsers]);

  return (
    <DashboardShell
      title="Users"
      subtitle="All accounts · roles · last sign-in"
      actions={
        <Button
          variant="ghost"
          size="md"
          iconLeft="refresh"
          onClick={() => void refresh()}
        >
          Refresh
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load users">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total users" value={kpis.total} hint="all accounts" />
        <KpiCard label="Active" value={kpis.active} hint="enabled" />
        <KpiCard label="Locked" value={kpis.locked} hint="5+ failed sign-ins" />
        <KpiCard label="Never signed in" value={kpis.neverSignedIn} hint="invited but idle" />
      </div>

      <Card padded={false} className="mt-6">
        <div className="flex flex-col gap-3 border-b border-ink-100 p-5 sm:flex-row sm:items-center sm:justify-between">
          <CardHeader
            eyebrow="Directory"
            title="All accounts"
            subtitle="Click a row to manage roles, password, and status."
          />
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name or email…"
              className="w-56 rounded-full border-0 bg-ink-100/60 px-4 py-2 text-sm text-ink-900 placeholder:text-ink-400 ring-1 ring-inset ring-ink-200 focus:bg-surface focus:ring-2 focus:ring-brand-500"
            />
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="rounded-full border-0 bg-ink-100/60 px-3 py-2 text-sm text-ink-900 ring-1 ring-inset ring-ink-200 focus:bg-surface focus:ring-2 focus:ring-brand-500"
            >
              <option value="">All roles</option>
              {ROLE_OPTIONS.map((r) => (
                <option key={r.code} value={r.code}>
                  {r.label}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-full border-0 bg-ink-100/60 px-3 py-2 text-sm text-ink-900 ring-1 ring-inset ring-ink-200 focus:bg-surface focus:ring-2 focus:ring-brand-500"
            >
              <option value="">All status</option>
              <option value="active">Active</option>
              <option value="disabled">Disabled</option>
              <option value="locked">Locked</option>
              <option value="never">Never signed in</option>
            </select>
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="p-10 text-center text-sm text-ink-500">
            {isLoading
              ? "Loading users…"
              : allUsers.length === 0
                ? "No users registered yet."
                : "No users match the current filters."}
          </div>
        ) : (
          <ul className="divide-y divide-ink-100">
            {filtered.map((u) => {
              const s = statusOf(u);
              return (
                <li
                  key={u.id}
                  className="flex cursor-pointer items-center gap-4 px-5 py-4 transition hover:bg-brand-50/30"
                  onClick={() => router.push(`/dashboard/users/${u.id}`)}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-ink-900">
                      {u.full_name || u.email}
                    </p>
                    <p className="truncate text-xs text-ink-500">{u.email}</p>
                  </div>
                  <div className="hidden w-44 text-right sm:block">
                    <p className="text-xs text-ink-500">Role</p>
                    <p className="text-sm font-semibold text-ink-900">
                      {u.primary_role
                        ? ROLE_OPTIONS.find((r) => r.code === u.primary_role)?.label ??
                          u.primary_role
                        : "—"}
                    </p>
                  </div>
                  <div className="hidden w-32 text-right sm:block">
                    <p className="text-xs text-ink-500">Last sign-in</p>
                    <p className="text-sm text-ink-900">{fmtRelative(u.last_login_at)}</p>
                  </div>
                  <Badge tone={s.tone} withDot>
                    {s.label}
                  </Badge>
                  <Link href={`/dashboard/users/${u.id}`}>
                    <Button
                      variant="ghost"
                      size="sm"
                      iconRight="chevron-right"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Manage
                    </Button>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </DashboardShell>
  );
}

function KpiCard({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <div className="rounded-3xl bg-surface p-5 ring-1 ring-ink-200 shadow-[var(--shadow-card)]">
      <p className="text-sm text-ink-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold tnum text-ink-900">{value}</p>
      <p className="mt-1 text-xs text-ink-500">{hint}</p>
    </div>
  );
}

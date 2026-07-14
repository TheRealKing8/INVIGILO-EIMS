/**
 * Notifications — the user's in-app event feed.
 *
 * One row per Notification the user has received. The topbar bell
 * counts unread; this page lists them all (read + unread) with
 * per-row "Mark read" and a "Mark all read" button. Each row's
 * ``target_url`` (set by the serializer) links the user to the
 * thing the notification is about — e.g. an allocation reassign
 * takes them to /dashboard/allocations/{id}.
 *
 * Empty state: "You're all caught up" + a friendly emoji-free copy.
 */
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  getNotifications,
  markAllRead,
  markRead,
  type Notification,
  type Paginated,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { useAuth } from "@/lib/auth";

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const kindLabel: Record<string, string> = {
  "allocation.reassigned": "Reassigned",
  "allocation.new": "New assignment",
  "incident.escalated": "Incident escalated",
  "incident.resolved": "Incident resolved",
  "session.rescheduled": "Session rescheduled",
  "session.cancelled": "Session cancelled",
};

const kindTone: Record<string, "brand" | "success" | "warning" | "danger" | "neutral"> = {
  "allocation.reassigned": "warning",
  "allocation.new": "success",
  "incident.escalated": "danger",
  "incident.resolved": "brand",
  "session.rescheduled": "warning",
  "session.cancelled": "danger",
};

export default function NotificationsPage() {
  const { user } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "unread">("all");

  const { data, isLoading, error, refresh } = useFetch<Paginated<Notification> | null>(
    () => getNotifications({ page_size: 50, ordering: "-created_at" }),
    [],
  );
  const items = data?.results ?? [];

  const visible = useMemo(
    () => items.filter((n) => (filter === "unread" ? !n.is_read : true)),
    [items, filter],
  );

  async function doMarkRead(id: string) {
    setActionError(null);
    setPending(id);
    try {
      await markRead(id);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not mark read");
    } finally {
      setPending(null);
    }
  }

  async function doMarkAllRead() {
    setActionError(null);
    setPending("__all__");
    try {
      await markAllRead();
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not mark all read");
    } finally {
      setPending(null);
    }
  }

  const unreadCount = items.filter((n) => !n.is_read).length;

  return (
    <DashboardShell
      title="Notifications"
      subtitle={
        unreadCount > 0
          ? `${unreadCount} unread · ${items.length} total`
          : `${items.length} total`
      }
      actions={
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="md"
            iconLeft="check"
            onClick={() => void doMarkAllRead()}
            disabled={pending === "__all__" || unreadCount === 0}
          >
            {pending === "__all__" ? "Marking…" : "Mark all read"}
          </Button>
        </div>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load notifications">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      {actionError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Action failed">
            {actionError}
          </StatusBanner>
        </div>
      ) : null}

      <div className="mb-6 flex flex-wrap items-center gap-2">
        {(
          [
            { value: "all", label: "All" },
            { value: "unread", label: "Unread" },
          ] as { value: "all" | "unread"; label: string }[]
        ).map((chip) => {
          const active = filter === chip.value;
          return (
            <button
              key={chip.value}
              type="button"
              onClick={() => setFilter(chip.value)}
              className={[
                "rounded-full px-4 py-1.5 text-sm font-medium transition",
                active
                  ? "bg-brand-700 text-white shadow-[var(--shadow-elev)]"
                  : "bg-surface text-ink-700 ring-1 ring-inset ring-ink-200 hover:bg-ink-100/60",
              ].join(" ")}
            >
              {chip.label}
              {chip.value === "unread" && unreadCount > 0 ? (
                <span className="ml-2 rounded-full bg-rose-500 px-1.5 text-[10px] font-semibold text-white">
                  {unreadCount}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      {isLoading && items.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-500">Loading…</p>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <CardHeader
            eyebrow="Inbox"
            title="You're all caught up"
            subtitle="New assignments, escalations, and reassignments show up here."
          />
        </Card>
      ) : visible.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-500">
            No unread notifications. {unreadCount === 0 ? "Mark some as unread to see them here." : null}
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {visible.map((n) => (
            <Card key={n.id} padded={false}>
              <div className="flex items-start gap-4 p-5">
                <div
                  className={[
                    "mt-1 h-2 w-2 shrink-0 rounded-full",
                    n.is_read ? "bg-transparent" : "bg-brand-700",
                  ].join(" ")}
                  aria-label={n.is_read ? "Read" : "Unread"}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={kindTone[n.kind] ?? "neutral"}>
                      {kindLabel[n.kind] ?? n.kind}
                    </Badge>
                    <p className="truncate text-sm font-semibold text-ink-900">
                      {n.title}
                    </p>
                    {n.email_failed ? (
                      <Badge tone="danger">email failed</Badge>
                    ) : n.email_sent_at ? (
                      <Badge tone="success">emailed</Badge>
                    ) : null}
                  </div>
                  {n.body ? (
                    <p className="mt-1 text-sm text-ink-700">{n.body}</p>
                  ) : null}
                  <div className="mt-2 flex items-center gap-3 text-xs text-ink-500">
                    <span>{fmtDateTime(n.created_at)}</span>
                    {n.target_url ? (
                      <Link
                        href={n.target_url}
                        className="font-semibold text-brand-700 underline"
                      >
                        Open
                      </Link>
                    ) : null}
                  </div>
                </div>
                {!n.is_read ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void doMarkRead(n.id)}
                    disabled={pending === n.id}
                  >
                    {pending === n.id ? "…" : "Mark read"}
                  </Button>
                ) : (
                  <span className="text-xs text-ink-400">
                    <Icon name="check" className="inline h-3.5 w-3.5" />
                  </span>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {!user ? null : (
        <p className="mt-8 flex items-center gap-2 text-xs text-ink-500">
          <Icon name="bell" className="h-3.5 w-3.5" />
          The bell at the top of every page shows your unread count.
        </p>
      )}
    </DashboardShell>
  );
}

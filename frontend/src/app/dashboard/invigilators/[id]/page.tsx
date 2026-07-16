/**
 * Invigilator profile — header, workload, 14-day availability grid,
 * and recent assignments.
 *
 * The grid is the main feature: each day-tile cycles through four
 * statuses (available → busy → off_duty → leave → available) and
 * POSTs the change to ``/api/v1/invigilators/availability/``. The
 * allocation engine reads those rows to filter candidates — see
 * ``backend/apps/allocations/services/engine.py:115-130`` — so what
 * a user does on this page directly affects who gets placed.
 */
"use client";

import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDark, CardHeader } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { ProgressBar } from "@/components/ui/viz";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  createExamSession,
  getActiveExamPeriod,
  getCourses,
  getRooms,
  type Course,
  type ExamPeriod,
  type Room,
} from "@/lib/api";
import {
  getAllocations,
  getAvailability,
  getInvigilators,
  setAvailability,
  staffQrUrl,
  staffQrUrlFor,
  type Allocation,
  type Availability,
  type InvigilatorProfile,
  type Paginated,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { useAuth } from "@/lib/auth";

type DayStatus = "available" | "busy" | "off_duty" | "leave";

const CYCLE: DayStatus[] = ["available", "busy", "off_duty", "leave"];
const NEXT: Record<DayStatus, DayStatus> = {
  available: "busy",
  busy: "off_duty",
  off_duty: "leave",
  leave: "available",
};

const statusBadgeTone: Record<DayStatus, "success" | "warning" | "danger" | "neutral"> = {
  available: "success",
  busy: "warning",
  off_duty: "danger",
  leave: "neutral",
};

const statusLabel: Record<DayStatus, string> = {
  available: "Available",
  busy: "Busy",
  off_duty: "Off duty",
  leave: "On leave",
};

/** Format YYYY-MM-DD as a stable ISO date string (no TZ shift). */
function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function dayLabel(d: Date): { weekday: string; dayNum: string; month: string } {
  return {
    weekday: d.toLocaleDateString([], { weekday: "short" }),
    dayNum: String(d.getDate()),
    month: d.toLocaleDateString([], { month: "short" }),
  };
}

function initialsOf(name: string | undefined, email: string | undefined): string {
  const source = (name || email || "??").trim();
  return source
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function fmtDay(iso: string): string {
  return new Date(iso).toLocaleDateString([], { month: "short", day: "2-digit" });
}

export default function InvigilatorProfilePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const { user: me } = useAuth();

  // The current status per date, indexed by YYYY-MM-DD. Built from
  // the server response on every refresh; we keep it as a Map so
  // lookups in the grid are O(1).
  const [statusByDate, setStatusByDate] = useState<Record<string, DayStatus>>({});
  const [pendingDate, setPendingDate] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  // Pull the profile, the 14-day availability window, and this
  // invigilator's allocations in parallel.
  const { data, isLoading, error, refresh } = useFetch<{
    profile: InvigilatorProfile | null;
    availability: Paginated<Availability> | null;
    allocations: Paginated<Allocation> | null;
  }>(
    async () => {
      if (!id) {
        return { profile: null, availability: null, allocations: null };
      }
      const today = new Date();
      const end = new Date(today);
      end.setDate(end.getDate() + 13);
      const [profilePage, availabilityPage, allocationPage] = await Promise.all([
        // The /profiles/ endpoint paginates; we filter to a single id
        // by hitting the list with a search term. If the API doesn't
        // support that filter, fall back to fetching the first page
        // and finding the row in the client.
        getInvigilators({ page: 1, page_size: 200 }).catch(() => null),
        getAvailability({
          invigilator: id,
          date__gte: isoDate(today),
          date__lte: isoDate(end),
        }).catch(() => null),
        getAllocations({ page: 1, page_size: 50, invigilator: id }).catch(() => null),
      ]);
      const profile =
        profilePage?.results.find((p) => p.id === id) ?? null;
      return { profile, availability: availabilityPage, allocations: allocationPage };
    },
    [id],
  );

  // Hydrate the status map whenever the availability page changes.
  // We re-derive the whole map on each refresh so the UI is the
  // source of truth for the current 14-day window.
  const serverStatusByDate: Record<string, DayStatus> = (() => {
    const out: Record<string, DayStatus> = {};
    for (const row of data?.availability?.results ?? []) {
      out[row.date] = row.status;
    }
    return out;
  })();

  // Merge: pendingDate takes precedence while a click is in flight;
  // otherwise fall back to the server state. This way the tile
  // updates optimistically as soon as the user clicks, without
  // waiting for the round-trip.
  const currentByDate: Record<string, DayStatus> = { ...serverStatusByDate, ...statusByDate };

  const profile = data?.profile ?? null;
  const allocations = data?.allocations?.results ?? [];
  const workload = allocations.length;
  // SA/EO/HR (people.invigilator.crud) can fetch *any* invigilator's
  // staff QR for verification. The server re-checks the perm on the
  // QR endpoint, so this is a client-side gate only.
  const canManageInvigilators = Boolean(
    me?.permissions?.includes("people.invigilator.crud"),
  );
  const cap = profile?.max_sessions_per_cycle ?? 0;

  // Build the 14-day window once per render. The window is anchored
  // to "today" at the moment this component renders, so the grid
  // slides forward as the user keeps the page open across midnight.
  const days: Date[] = (() => {
    const list: Date[] = [];
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    for (let i = 0; i < 14; i += 1) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      list.push(d);
    }
    return list;
  })();

  async function cycleStatus(date: string) {
    if (!id) return;
    const current = currentByDate[date] ?? "available";
    const next = NEXT[current];
    setStatusByDate((prev) => ({ ...prev, [date]: next }));
    setPendingDate(date);
    setActionError(null);
    try {
      await setAvailability({ invigilator: id, date, status: next });
      // Re-fetch the availability window so we end up exactly aligned
      // with the server's view (a 400 on duplicate would otherwise
      // silently leave us out of sync).
      await refresh();
      setStatusByDate((prev) => {
        const { [date]: _drop, ...rest } = prev;
        return rest;
      });
    } catch (err) {
      // Roll back the optimistic update.
      setStatusByDate((prev) => {
        const { [date]: _drop, ...rest } = prev;
        return rest;
      });
      setActionError(
        err instanceof Error ? err.message : "We couldn't update your availability.",
      );
    } finally {
      setPendingDate(null);
    }
  }

  return (
    <DashboardShell
      title={profile ? profile.user_full_name ?? profile.user_email ?? "Invigilator" : "Invigilator"}
      subtitle={profile ? (profile.user_email ?? "—") : "Profile"}
      actions={
        <Button
          variant="ghost"
          size="md"
          iconLeft="arrow-right"
          onClick={() => router.push("/dashboard/invigilators")}
        >
          <span className="-mt-px inline-block rotate-180">Back to roster</span>
        </Button>
      }
    >
      {error ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Could not load invigilator">
            {error.message}
          </StatusBanner>
        </div>
      ) : null}

      {actionError ? (
        <div className="mb-6">
          <StatusBanner tone="danger" title="Availability update failed">
            {actionError}
          </StatusBanner>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        {/* Header + availability ----------------------------------- */}
        <div className="space-y-6">
          <Card>
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-brand-700 text-base font-semibold text-white">
                {initialsOf(profile?.user_full_name, profile?.user_email)}
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-xl font-semibold text-ink-900">
                  {profile?.user_full_name ?? (isLoading ? "Loading…" : "Unknown invigilator")}
                </h2>
                <p className="text-sm text-ink-500">
                  {profile?.user_email ?? "—"}
                </p>
                <p className="mt-0.5 text-xs text-ink-500">
                  {profile?.primary_department_name ?? profile?.primary_department_code ?? "No department"}
                  {" · "}
                  max {profile?.max_sessions_per_cycle ?? "—"} sessions/cycle
                  {" · "}
                  {parseFloat(profile?.rating ?? "0").toFixed(2)} ★
                </p>
              </div>
              <Badge tone={profile?.is_active ? "success" : "neutral"} withDot>
                {profile?.is_active ? "Active" : "Inactive"}
              </Badge>
              <Button
                variant="primary"
                size="sm"
                iconLeft="plus"
                onClick={() => setShowCreate((v) => !v)}
              >
                {showCreate ? "Hide form" : "Create session"}
              </Button>
            </div>

            {showCreate ? (
              <CreateSessionInline
                invigilatorId={id}
                onCreated={() => {
                  setShowCreate(false);
                  void refresh();
                }}
              />
            ) : null}
          </Card>

          <Card padded={false}>
            <div className="border-b border-ink-100 p-5">
              <CardHeader
                eyebrow="Availability"
                title="Next 14 days"
                subtitle="Tap a day to cycle through statuses. The allocation engine reads these rows to decide who can be placed."
              />
            </div>

            <div className="grid grid-cols-4 gap-2 p-4 sm:grid-cols-7">
              {days.map((d) => {
                const dateStr = isoDate(d);
                const status = currentByDate[dateStr] ?? "available";
                const { weekday, dayNum, month } = dayLabel(d);
                const isPending = pendingDate === dateStr;
                return (
                  <button
                    key={dateStr}
                    type="button"
                    onClick={() => void cycleStatus(dateStr)}
                    disabled={isPending}
                    className="group flex flex-col items-center gap-1.5 rounded-2xl bg-surface p-3 text-center ring-1 ring-inset ring-ink-200 transition hover:ring-brand-400 disabled:opacity-60"
                  >
                    <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-500">
                      {weekday}
                    </span>
                    <span className="text-lg font-semibold tnum text-ink-900">
                      {dayNum}
                    </span>
                    <span className="text-[10px] text-ink-400">{month}</span>
                    <Badge tone={statusBadgeTone[status]} withDot className="mt-1">
                      {isPending ? "Saving…" : statusLabel[status]}
                    </Badge>
                  </button>
                );
              })}
            </div>

            <div className="flex flex-wrap items-center gap-3 border-t border-ink-100 px-5 py-3 text-xs text-ink-500">
              <span className="font-semibold">Legend:</span>
              {CYCLE.map((s) => (
                <span key={s} className="inline-flex items-center gap-1.5">
                  <Badge tone={statusBadgeTone[s]} withDot>
                    {statusLabel[s]}
                  </Badge>
                </span>
              ))}
            </div>
          </Card>

          {/* Recent assignments ------------------------------------ */}
          <Card padded={false}>
            <div className="border-b border-ink-100 p-5">
              <CardHeader
                eyebrow="Assignments"
                title="Recent allocations"
                subtitle="Sessions this invigilator is currently assigned to."
              />
            </div>

            {allocations.length === 0 ? (
              <div className="p-8 text-center text-sm text-ink-500">
                {isLoading ? "Loading assignments…" : "No assignments yet. Run the allocation engine to assign this invigilator to a session."}
              </div>
            ) : (
              <ul className="divide-y divide-ink-100">
                {allocations.map((a) => (
                  <li
                    key={a.id}
                    className="flex items-center gap-4 px-5 py-3 transition hover:bg-brand-50/30"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-ink-900">
                        {a.exam_code ?? "Session"}
                      </p>
                      <p className="text-xs text-ink-500">
                        {a.exam_title ?? "—"}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-ink-500">{a.session_starts_at ? fmtDay(a.session_starts_at) : "—"}</p>
                      <p className="text-xs text-ink-500 tnum">
                        {a.session_starts_at ? fmtTime(a.session_starts_at) : ""}
                      </p>
                    </div>
                    <Badge tone={a.status === "confirmed" ? "success" : a.status === "rejected" ? "danger" : "warning"} withDot>
                      {a.status === "draft" ? "Pending" : a.status}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* Workload + AI nudge -------------------------------------- */}
        <div className="space-y-6">
          <Card>
            <CardHeader eyebrow="Workload" title="Cycle cap utilisation" />
            <div className="mt-5">
              <div className="flex items-center justify-between text-sm text-ink-700">
                <span className="font-semibold">{workload} of {cap || "—"}</span>
                <span className="tnum text-ink-500">
                  {cap > 0 ? Math.round((workload / cap) * 100) : 0}%
                </span>
              </div>
              <ProgressBar
                value={cap > 0 ? (workload / cap) * 100 : 0}
                tone={cap > 0 && workload > cap * 0.9 ? "warning" : "brand"}
                className="mt-2"
              />
              <p className="mt-2 text-xs text-ink-500">
                {cap > 0
                  ? workload >= cap
                    ? "At the cycle cap. The engine will skip this invigilator for new runs."
                    : `${cap - workload} session${cap - workload === 1 ? "" : "s"} of headroom this cycle.`
                  : "No cap configured."}
              </p>
            </div>
          </Card>

          {/* Phase 19 + 20: staff QR panel.
              * Self: anyone signed in (no extra perm).
              * Operator: SA/EO/HR (people.invigilator.crud) can fetch
                another invigilator's QR. The token is still minted
                for the *target* user, so a screenshot of their
                QR still checks THEM in. */}
          {profile && id && (profile.user === me?.id || canManageInvigilators) ? (
            <StaffQrPanel profileId={id} isSelf={profile.user === me?.id} />
          ) : null}

          <CardDark>
            <p className="eyebrow text-brand-300">Allocation engine</p>
            <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">
              How your availability is used
            </h3>
            <p className="mt-2 text-sm text-brand-100/80">
              The engine treats <em>available</em> as the default. Any non-available
              row on a session date removes you from the candidate pool for that
              date — even if you&apos;re under the cycle cap. Mark yourself
              <em> busy</em> or <em>off duty</em> early so the officer running the
              engine can pick another invigilator without you being silently
              skipped.
            </p>
            <div className="mt-5">
              <Icon name="calendar" className="h-8 w-8 text-brand-300" />
            </div>
          </CardDark>
        </div>
      </div>
    </DashboardShell>
  );
}

/**
 * "Staff QR" — Phase 19 + Phase 20. The panel renders in two cases:
 *
 *  1. **Self**: the viewed profile is the *currently signed-in*
 *     user. Anyone can fetch their own staff QR; this is the
 *     primary use-case.
 *  2. **Operator view**: the viewer has ``people.invigilator.crud``
 *     (admin / EO / HR). They can fetch *another* invigilator's
 *     QR for verification — the token is still minted for the
 *     *target* user, not the viewer, so scanning the QR still
 *     checks in the right person.
 *
 * In both cases the PNG is fetched from a signed endpoint and
 * the ``?t=`` cache-buster rotates every 60s, so a screenshot
 * of this page is stale within a minute. The signed TTL on the
 * server is 5min, so the 60s rotation gives comfortable headroom.
 */
function StaffQrPanel({
  profileId,
  isSelf,
}: {
  profileId: string;
  isSelf: boolean;
}) {
  // Cache-buster every minute → 5min TTL + 1min rotation.
  const [stamp, setStamp] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setStamp(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);
  const base = isSelf ? staffQrUrl() : staffQrUrlFor(profileId);
  const src = `${base}?t=${stamp}`;
  return (
    <Card>
      <CardHeader
        eyebrow={isSelf ? "My staff QR" : "Staff QR"}
        title={isSelf ? "Show this at the door" : "Their staff QR"}
        subtitle={
          isSelf
            ? "Rotates every 60 seconds. Tied to your account — don't share it."
            : "Tied to this invigilator's account. Scanning checks THEM in, not you."
        }
      />
      <div className="mt-4 flex justify-center rounded-2xl bg-white p-4 ring-1 ring-ink-200">
        <img
          src={src}
          alt="Staff QR code"
          width={192}
          height={192}
          className="h-48 w-48"
        />
      </div>
      <p className="mt-3 text-xs text-ink-500">
        The security officer scans this with the door scanner; the scanner
        checks the signature and creates a check-in. 5-minute validity,
        60-second rotation.
      </p>
    </Card>
  );
}

/**
 * Inline form for an invigilator to add a new exam session and
 * auto-allocate themselves. Submitted as a child of the profile
 * card; on success it calls `onCreated` so the parent can close
 * the form and refresh the assignments card.
 */
function CreateSessionInline({
  invigilatorId,
  onCreated,
}: {
  invigilatorId: string | undefined;
  onCreated: () => void;
}) {
  const router = useRouter();
  const [courseId, setCourseId] = useState("");
  const [roomId, setRoomId] = useState("");
  const [start, setStart] = useState("");
  const [duration, setDuration] = useState("120");
  const [capacity, setCapacity] = useState("60");
  const [invigilatorsRequired, setInvigilatorsRequired] = useState("1");
  const [special, setSpecial] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: coursesPage } = useFetch(() => getCourses({ page_size: 100 }), []);
  const { data: roomsPage } = useFetch(() => getRooms({ page_size: 100 }), []);
  const { data: activePeriod } = useFetch(() => getActiveExamPeriod(), []);
  const courses: Course[] = coursesPage?.results ?? [];
  const rooms: Room[] = roomsPage?.results ?? [];

  const canSubmit =
    !!courseId && !!start && !!duration && Number(capacity) > 0 && !!activePeriod;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit || !activePeriod) return;
    setError(null);
    setSubmitting(true);
    try {
      const startIso = new Date(start).toISOString();
      const endIso = new Date(new Date(start).getTime() + Number(duration) * 60_000).toISOString();
      const created = await createExamSession({
        period: activePeriod.id,
        course: courseId,
        room: roomId || null,
        starts_at: startIso,
        ends_at: endIso,
        capacity: Number(capacity),
        registered: 0,
        invigilators_required: Number(invigilatorsRequired),
        status: "draft",
        special_requirements: special || undefined,
      });
      onCreated();
      router.push(`/dashboard/exams/${created.id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not create the session. Please check the fields and try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-5 grid gap-4 border-t border-ink-100 pt-5 sm:grid-cols-2"
    >
      {error ? (
        <div className="sm:col-span-2">
          <StatusBanner tone="danger" title="Could not create the session">
            {error}
          </StatusBanner>
        </div>
      ) : null}
      <div>
        <label htmlFor="cs-course" className="mb-1.5 block text-sm font-medium text-ink-700">
          Course <span className="text-rose-600">*</span>
        </label>
        <select
          id="cs-course"
          value={courseId}
          onChange={(e) => setCourseId(e.target.value)}
          required
          className="block w-full appearance-none rounded-2xl border-0 bg-ink-100/60 px-4 py-3 text-sm text-ink-900 ring-1 ring-inset ring-ink-200 transition focus:bg-surface focus:ring-2 focus:ring-brand-500"
        >
          <option value="">Pick a course…</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} — {c.title}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="cs-room" className="mb-1.5 block text-sm font-medium text-ink-700">
          Room
        </label>
        <select
          id="cs-room"
          value={roomId}
          onChange={(e) => setRoomId(e.target.value)}
          className="block w-full appearance-none rounded-2xl border-0 bg-ink-100/60 px-4 py-3 text-sm text-ink-900 ring-1 ring-inset ring-ink-200 transition focus:bg-surface focus:ring-2 focus:ring-brand-500"
        >
          <option value="">No room assigned</option>
          {rooms.map((r) => (
            <option key={r.id} value={r.id}>
              {r.code} — {r.name} (cap {r.capacity})
            </option>
          ))}
        </select>
      </div>
      <Input
        id="cs-start"
        name="cs-start"
        label="Starts at"
        type="datetime-local"
        value={start}
        onChange={(e) => setStart(e.target.value)}
        required
        iconLeft="calendar"
      />
      <Input
        id="cs-duration"
        name="cs-duration"
        label="Duration (minutes)"
        type="number"
        min={1}
        value={duration}
        onChange={(e) => setDuration(e.target.value)}
        required
      />
      <Input
        id="cs-capacity"
        name="cs-capacity"
        label="Capacity"
        type="number"
        min={1}
        value={capacity}
        onChange={(e) => setCapacity(e.target.value)}
        required
      />
      <Input
        id="cs-required"
        name="cs-required"
        label="Invigilators required"
        type="number"
        min={1}
        value={invigilatorsRequired}
        onChange={(e) => setInvigilatorsRequired(e.target.value)}
        required
      />
      <div className="sm:col-span-2">
        <label htmlFor="cs-special" className="mb-1.5 block text-sm font-medium text-ink-700">
          Special requirements
        </label>
        <textarea
          id="cs-special"
          name="cs-special"
          rows={2}
          value={special}
          onChange={(e) => setSpecial(e.target.value)}
          className="block w-full rounded-2xl border-0 bg-ink-100/60 px-4 py-3 text-sm text-ink-900 ring-1 ring-inset ring-ink-200 transition focus:bg-surface focus:ring-2 focus:ring-brand-500"
        />
      </div>
      <div className="flex items-center justify-end gap-2 sm:col-span-2">
        <Button
          type="submit"
          size="sm"
          variant="primary"
          iconLeft="plus"
          loading={submitting}
          disabled={!canSubmit || submitting}
        >
          {submitting ? "Creating…" : "Create & auto-allocate"}
        </Button>
      </div>
      {invigilatorId ? (
        <p className="sm:col-span-2 text-[11px] text-ink-500">
          You will be auto-allocated as the chief invigilator for this session.
        </p>
      ) : null}
    </form>
  );
}

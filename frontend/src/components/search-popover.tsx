/**
 * SearchPopover — the type-ahead results panel that hangs off the
 * Topbar's search input. When the user types at least 2 characters,
 * we fan out to three list endpoints in parallel
 * (exams, invigilators, rooms), each capped at 5 results, and render
 * them as three grouped sections. Each row is a link to the relevant
 * detail page.
 *
 * The popover does NOT own the input — the input lives in the Topbar
 * and passes its current `query` in. When a row is selected, the
 * Topbar clears the query and we call `onClose()` to dismiss.
 */
"use client";

import { useEffect, useState, type RefObject } from "react";
import { useRouter } from "next/navigation";

import { getExamSessions, getInvigilators, getRooms, type ExamSession, type InvigilatorProfile, type Room } from "@/lib/api";
import { Icon, type IconName } from "@/components/ui/icon";

type Section = "exams" | "invigilators" | "rooms";

const DEBOUNCE_MS = 200;
const MIN_CHARS = 2;
const PER_SECTION = 5;

type State = {
  exams: ExamSession[];
  invigilators: InvigilatorProfile[];
  rooms: Room[];
  loading: boolean;
  error: string | null;
};

function emptyState(): State {
  return { exams: [], invigilators: [], rooms: [], loading: false, error: null };
}

export function SearchPopover({
  query,
  onClose,
  containerRef,
}: {
  query: string;
  onClose: () => void;
  /**
   * Ref of the wrapper that contains BOTH the search input and this
   * popover. We use it for the click-outside check so that clicking
   * the input (which is outside the popover's own <div>) does NOT
   * dismiss the popover.
   */
  containerRef?: RefObject<HTMLDivElement | null>;
}) {
  const router = useRouter();
  const [state, setState] = useState<State>(emptyState());

  // Don't fire until the user has typed enough to be specific.
  const trimmed = query.trim();
  const enabled = trimmed.length >= MIN_CHARS;

  useEffect(() => {
    if (!enabled) {
      setState(emptyState());
      return;
    }
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    const handle = window.setTimeout(async () => {
      try {
        const [examsR, invsR, roomsR] = await Promise.all([
          getExamSessions({ search: trimmed, page_size: PER_SECTION }).catch((err) => {
            throw err;
          }),
          getInvigilators({ search: trimmed, page_size: PER_SECTION }).catch((err) => {
            throw err;
          }),
          getRooms({ search: trimmed, page_size: PER_SECTION }).catch((err) => {
            throw err;
          }),
        ]);
        if (cancelled) return;
        setState({
          exams: examsR.results ?? [],
          invigilators: invsR.results ?? [],
          rooms: roomsR.results ?? [],
          loading: false,
          error: null,
        });
      } catch (err) {
        if (cancelled) return;
        setState({
          exams: [],
          invigilators: [],
          rooms: [],
          loading: false,
          error: err instanceof Error ? err.message : String(err),
        });
      }
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [trimmed, enabled]);

  // Click-outside dismisses the popover (Topbar handles Escape).
  // We listen on `click` (not `mousedown`) so the click handler on a
  // result row fires first; this lets the row navigate before the
  // popover tears down its own DOM. We also check the click target
  // against the OUTER container (input + popover) so a click on the
  // input — which is outside the popover's own <div> — does NOT
  // close the popover.
  useEffect(() => {
    function onClick(e: MouseEvent) {
      const root = containerRef?.current;
      const t = e.target as Node | null;
      if (root && t && root.contains(t)) return;
      onClose();
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, [onClose, containerRef]);

  if (!enabled) return null;

  const total =
    state.exams.length + state.invigilators.length + state.rooms.length;

  function pickAndClose(href: string) {
    onClose();
    router.push(href);
  }

  return (
    <div
      role="listbox"
      aria-label="Search results"
      className="absolute left-0 right-0 top-full z-40 mt-2 max-h-[70vh] overflow-auto rounded-2xl bg-surface shadow-[var(--shadow-elev)] ring-1 ring-ink-200"
    >
      {state.loading ? (
        <p className="px-5 py-4 text-sm text-ink-500">
          Searching for <span className="font-semibold text-ink-900">"{trimmed}"</span>…
        </p>
      ) : state.error ? (
        <p className="px-5 py-4 text-sm text-rose-700">
          Search failed: {state.error}
        </p>
      ) : total === 0 ? (
        <p className="px-5 py-4 text-sm text-ink-500">
          No results for <span className="font-semibold text-ink-900">"{trimmed}"</span>.
          Try a course code, name, or room code.
        </p>
      ) : (
        <div className="divide-y divide-ink-100">
          <Section
            title="Exams"
            icon="calendar"
            count={state.exams.length}
            visible={state.exams.length > 0}
          >
            {state.exams.map((e) => (
              <ResultRow
                key={e.id}
                icon="calendar"
                primary={e.course_code ?? "—"}
                secondary={e.course_title ?? ""}
                meta={[
                  e.room_code ? `Room ${e.room_code}` : null,
                  e.faculty_code ?? null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
                onClick={() => pickAndClose(`/dashboard/exams/${e.id}`)}
              />
            ))}
          </Section>

          <Section
            title="Invigilators"
            icon="users"
            count={state.invigilators.length}
            visible={state.invigilators.length > 0}
          >
            {state.invigilators.map((p) => (
              <ResultRow
                key={p.id}
                icon="users"
                primary={p.user_full_name ?? p.user_email ?? "Invigilator"}
                secondary={p.primary_department_name ?? p.primary_department_code ?? ""}
                meta={p.user_email ?? ""}
                onClick={() => pickAndClose(`/dashboard/invigilators/${p.id}`)}
              />
            ))}
          </Section>

          <Section
            title="Rooms"
            icon="map-pin"
            count={state.rooms.length}
            visible={state.rooms.length > 0}
          >
            {state.rooms.map((r) => (
              <ResultRow
                key={r.id}
                icon="map-pin"
                primary={r.code}
                secondary={r.name}
                meta={[
                  r.building_name ?? r.building_code ?? null,
                  r.capacity ? `Cap ${r.capacity}` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
                onClick={() => pickAndClose(`/dashboard/exams?room=${r.id}`)}
              />
            ))}
          </Section>
        </div>
      )}

      <div className="flex items-center justify-between border-t border-ink-100 bg-ink-100/40 px-5 py-2 text-[11px] text-ink-500">
        <span>
          {total} result{total === 1 ? "" : "s"} · live from the API
        </span>
        <span className="hidden sm:inline">⏎ to dismiss</span>
      </div>
    </div>
  );
}

function Section({
  title,
  icon,
  count,
  visible,
  children,
}: {
  title: string;
  icon: IconName;
  count: number;
  visible: boolean;
  children: React.ReactNode;
}) {
  if (!visible) return null;
  return (
    <div className="p-2">
      <div className="flex items-center gap-2 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-500">
        <Icon name={icon} className="h-3.5 w-3.5" />
        {title}
        <span className="tnum text-ink-400">({count})</span>
      </div>
      <ul className="space-y-0.5">{children}</ul>
    </div>
  );
}

function ResultRow({
  icon,
  primary,
  secondary,
  meta,
  onClick,
}: {
  icon: IconName;
  primary: string;
  secondary: string;
  meta: string;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition hover:bg-brand-50/60"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink-100 text-ink-700 ring-1 ring-inset ring-ink-200">
          <Icon name={icon} className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink-900">
            {primary}
          </p>
          {secondary ? (
            <p className="truncate text-xs text-ink-500">{secondary}</p>
          ) : null}
        </div>
        {meta ? (
          <span className="hidden truncate text-[11px] text-ink-500 sm:inline">
            {meta}
          </span>
        ) : null}
        <Icon name="arrow-right" className="h-3.5 w-3.5 shrink-0 text-ink-400" />
      </button>
    </li>
  );
}

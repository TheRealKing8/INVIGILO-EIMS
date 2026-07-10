/**
 * ThemeToggle — small icon button that opens a 3-item dropdown
 * (System / Light / Dark). Sits in the dashboard topbar and the
 * mobile nav drawer.
 *
 * Visual model: the button itself always shows the *resolved* theme
 * (sun if the page is light, moon if dark, monitor if system) so the
 * icon is honest about what's currently rendered. The dropdown shows
 * the user's *choice* (highlighted), not the resolved theme.
 */

"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "@/components/ui/icon";
import { useTheme, type ThemeChoice } from "@/lib/theme";

type ThemeOption = {
  value: ThemeChoice;
  label: string;
  hint: string;
  icon: "sun" | "moon" | "monitor";
};

const OPTIONS: ThemeOption[] = [
  { value: "system", label: "System", hint: "Follow OS", icon: "monitor" },
  { value: "light", label: "Light", hint: "Always light", icon: "sun" },
  { value: "dark", label: "Dark", hint: "Always dark", icon: "moon" },
];

function ChevronIcon({ className }: { className?: string }) {
  // Small caret under the toggle that shows the dropdown is open.
  return (
    <svg
      viewBox="0 0 12 12"
      aria-hidden
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 5l3 3 3-3" />
    </svg>
  );
}

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const buttonId = useId();
  const menuId = useId();

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // The button icon reflects the resolved theme (what's actually painted).
  const buttonIcon = resolvedTheme === "dark" ? "moon" : "sun";

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      <button
        id={buttonId}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Theme: ${theme}. Click to change.`}
        className="relative inline-flex h-11 items-center gap-1 rounded-full bg-ink-100/60 pl-3 pr-2.5 text-ink-700 ring-1 ring-inset ring-ink-200 transition hover:bg-surface focus-visible:bg-surface"
      >
        <Icon name={buttonIcon} className="h-4 w-4" />
        <ChevronIcon className="h-3 w-3 opacity-70" />
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-labelledby={buttonId}
          className="absolute right-0 z-40 mt-2 w-56 overflow-hidden rounded-2xl bg-surface p-1 shadow-[var(--shadow-elev)] ring-1 ring-ink-200"
        >
          {OPTIONS.map((opt) => {
            const isActive = theme === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                role="menuitemradio"
                aria-checked={isActive}
                onClick={() => {
                  setTheme(opt.value);
                  setOpen(false);
                }}
                className={[
                  "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition",
                  isActive
                    ? "bg-brand-50 text-brand-800 dark:bg-brand-900/30 dark:text-brand-200"
                    : "text-ink-700 hover:bg-ink-100 dark:hover:bg-ink-100/60",
                ].join(" ")}
              >
                <span
                  className={[
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl",
                    isActive
                      ? "bg-brand-700 text-white"
                      : "bg-ink-100 text-ink-700 dark:bg-ink-100/60 dark:text-ink-200",
                  ].join(" ")}
                >
                  <Icon name={opt.icon} className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold">{opt.label}</span>
                  <span className="block text-[11px] text-ink-500">{opt.hint}</span>
                </span>
                {isActive ? (
                  <Icon name="check" className="h-4 w-4 text-brand-700 dark:text-brand-300" />
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

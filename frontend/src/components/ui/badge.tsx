/**
 * Badge — small status pill.
 *
 *   <Badge tone="success">Confirmed</Badge>
 *
 * Tones map to the brand palette so the rest of the app doesn't have
 * to reach for raw emerald/rose/amber Tailwind classes.
 */
import { type ReactNode } from "react";

export type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

const toneClass: Record<Tone, string> = {
  neutral: "bg-ink-100 text-ink-700 ring-ink-200",
  brand:   "bg-brand-50 text-brand-800 ring-brand-200",
  success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  warning: "bg-amber-50 text-amber-700 ring-amber-200",
  danger:  "bg-rose-50 text-rose-700 ring-rose-200",
  info:    "bg-sky-50 text-sky-700 ring-sky-200",
};

const dotClass: Record<Tone, string> = {
  neutral: "bg-ink-400",
  brand:   "bg-brand-500",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger:  "bg-rose-500",
  info:    "bg-sky-500",
};

export function Badge({
  tone = "neutral",
  children,
  withDot = false,
  className = "",
}: {
  tone?: Tone;
  children: ReactNode;
  withDot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset",
        toneClass[tone],
        className,
      ].join(" ")}
    >
      {withDot ? (
        <span className={`h-1.5 w-1.5 rounded-full ${dotClass[tone]}`} aria-hidden />
      ) : null}
      {children}
    </span>
  );
}

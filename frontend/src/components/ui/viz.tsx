/**
 * Bar — a small data-viz primitive used on the dashboard.
 *
 * Used in pairs: one wide "percentage completion" bar and several
 * "today's allocation" bars. Kept inline so we don't pull in a charting
 * library for a few dozen bars.
 */
import { type ReactNode } from "react";

export function ProgressBar({
  value,
  max = 100,
  tone = "brand",
  className = "",
}: {
  value: number;
  max?: number;
  tone?: "brand" | "success" | "warning" | "danger";
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const fill: Record<typeof tone, string> = {
    brand: "bg-brand-600",
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    danger: "bg-rose-500",
  };
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-ink-100 ${className}`}>
      <div
        className={`h-full ${fill[tone]} transition-all duration-700`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function MiniBar({
  values,
  max,
  tone = "brand",
  labels,
}: {
  values: number[];
  max?: number;
  tone?: "brand" | "success" | "warning" | "danger";
  labels?: string[];
}) {
  const cap = max ?? Math.max(...values, 1);
  const fill: Record<typeof tone, string> = {
    brand: "bg-brand-600",
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    danger: "bg-rose-500",
  };
  return (
    <div className="flex h-32 items-end gap-2">
      {values.map((v, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-2">
          <div className="flex h-full w-full items-end">
            <div
              className={`w-full rounded-t-md ${fill[tone]}`}
              style={{ height: `${(v / cap) * 100}%`, minHeight: v > 0 ? 4 : 0 }}
            />
          </div>
          {labels?.[i] ? (
            <span className="text-[10px] font-medium text-ink-500">{labels[i]}</span>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function Sparkline({
  values,
  width = 96,
  height = 28,
  tone = "brand",
}: {
  values: number[];
  width?: number;
  height?: number;
  tone?: "brand" | "success" | "warning" | "danger";
}) {
  if (values.length === 0) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1 || 1);
  const path = values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / range) * height;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  const stroke: Record<typeof tone, string> = {
    brand: "#047857",
    success: "#10b981",
    warning: "#f59e0b",
    danger: "#f43f5e",
  };
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <path d={path} fill="none" stroke={stroke[tone]} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function StatRow({ children }: { children: ReactNode }) {
  return <div className="divide-y divide-ink-100">{children}</div>;
}

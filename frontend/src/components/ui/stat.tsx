/**
 * Stat — the dashboard tile primitive.
 *
 * A single source of truth for the look of every "big number on a
 * small card" tile. Used on the dashboard home and the module pages.
 *
 * Pass `href` to make the tile a clickable link (navigates the
 * router to that page), or `onClick` to make it a button. When
 * neither is set the tile is static — the existing call sites
 * remain visually unchanged. The hover lift + ring animation runs
 * only when the tile is interactive.
 */
import Link from "next/link";
import { type ReactNode } from "react";
import { Icon, type IconName } from "@/components/ui/icon";
import { Badge, type Tone } from "@/components/ui/badge";

type StatProps = {
  label: string;
  value: string;
  delta?: { value: string; tone: "up" | "down" | "flat" };
  icon?: IconName;
  iconTone?: "brand" | "dark";
  hint?: string;
  href?: string;
  onClick?: () => void;
};

const deltaTone: Record<"up" | "down" | "flat", Tone> = {
  up: "success",
  down: "danger",
  flat: "neutral",
};

const deltaIcon: Record<"up" | "down" | "flat", IconName> = {
  up: "arrow-up-right",
  down: "arrow-down-right",
  flat: "arrow-right",
};

const interactiveClass =
  "transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[var(--shadow-elev)] " +
  "hover:ring-brand-300 active:scale-[0.98] cursor-pointer block w-full text-left";

export function Stat({
  label,
  value,
  delta,
  icon,
  iconTone = "brand",
  hint,
  href,
  onClick,
}: StatProps) {
  const inner = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-ink-500">{label}</p>
        {icon ? (
          <div
            className={[
              "flex h-9 w-9 items-center justify-center rounded-2xl",
              iconTone === "brand"
                ? "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100"
                : "bg-surface-dark text-brand-300 ring-1 ring-inset ring-white/10",
            ].join(" ")}
          >
            <Icon name={icon} className="h-4 w-4" />
          </div>
        ) : null}
      </div>
      <p className="mt-3 text-3xl font-semibold tnum tracking-tight text-ink-900">
        {value}
      </p>
      <div className="mt-2 flex items-center gap-2">
        {delta ? (
          <Badge tone={deltaTone[delta.tone]} withDot>
            <Icon name={deltaIcon[delta.tone]} className="h-3 w-3" />
            {delta.value}
          </Badge>
        ) : null}
        {hint ? <p className="text-xs text-ink-500">{hint}</p> : null}
      </div>
      {href || onClick ? (
        <div className="mt-3 flex items-center justify-end text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-700">
          View
          <Icon name="arrow-right" className="ml-1 h-3 w-3" />
        </div>
      ) : null}
    </>
  );

  const baseClass =
    "rounded-3xl bg-surface p-5 ring-1 ring-ink-200 shadow-[var(--shadow-card)]";

  if (href) {
    return (
      <Link href={href} className={`${baseClass} ${interactiveClass}`}>
        {inner}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${baseClass} ${interactiveClass}`}
      >
        {inner}
      </button>
    );
  }
  return <div className={baseClass}>{inner}</div>;
}

/**
 * HeroStat — the larger, dark variant used for the "Today's overview"
 * panel on the dashboard. Same shape as Stat but inverted.
 */
export function HeroStat({
  label,
  value,
  sub,
  icon,
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: IconName;
}) {
  return (
    <div className="rounded-2xl bg-white/[0.04] p-4 ring-1 ring-inset ring-white/10">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-300/90">
          {label}
        </p>
        {icon ? <Icon name={icon} className="h-4 w-4 text-brand-300" /> : null}
      </div>
      <p className="mt-3 text-3xl font-semibold tnum tracking-tight text-white">
        {value}
      </p>
      {sub ? <p className="mt-1 text-xs text-brand-200/70">{sub}</p> : null}
    </div>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{children}</div>;
}

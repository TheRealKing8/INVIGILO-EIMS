/**
 * Stat — the dashboard tile primitive.
 *
 * A single source of truth for the look of every "big number on a
 * small card" tile. Used on the dashboard home and the module pages.
 */
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

export function Stat({ label, value, delta, icon, iconTone = "brand", hint }: StatProps) {
  return (
    <div className="rounded-3xl bg-surface p-5 ring-1 ring-ink-200 shadow-[var(--shadow-card)]">
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
    </div>
  );
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

/**
 * Card — the basic surface that holds everything.
 *
 * - `Card`        — white surface with the soft, brand-tinted shadow
 * - `CardHeader`  — header with a title + optional eyebrow + actions
 * - `CardSection` — body wrapper; gives a consistent internal rhythm
 * - `CardDark`    — emerald-950 surface with white text (hero panels)
 */
import { type HTMLAttributes, type ReactNode } from "react";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  padded?: boolean;
};

export function Card({ children, className = "", padded = true, ...rest }: CardProps) {
  return (
    <div
      {...rest}
      className={[
        "rounded-3xl bg-surface ring-1 ring-ink-200 shadow-[var(--shadow-card)]",
        padded ? "p-6" : "",
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}

export function CardDark({
  children,
  className = "",
  padded = true,
  ...rest
}: CardProps) {
  return (
    <div
      {...rest}
      className={[
        "rounded-3xl bg-surface-dark text-white ring-1 ring-white/5 shadow-[var(--shadow-elev)]",
        "relative overflow-hidden",
        padded ? "p-6" : "",
        className,
      ].join(" ")}
    >
      <div className="dot-bg pointer-events-none absolute inset-0 opacity-60" aria-hidden />
      <div className="relative">{children}</div>
    </div>
  );
}

type CardHeaderProps = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
};

export function CardHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  className = "",
}: CardHeaderProps) {
  return (
    <div className={`flex items-start justify-between gap-6 ${className}`}>
      <div className="min-w-0">
        {eyebrow ? (
          <p className="eyebrow text-brand-700">{eyebrow}</p>
        ) : null}
        <h2 className="mt-1 text-xl font-semibold tracking-tight text-ink-900">
          {title}
        </h2>
        {subtitle ? (
          <p className="mt-1 text-sm text-ink-500">{subtitle}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function CardSection({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={className}>{children}</div>;
}

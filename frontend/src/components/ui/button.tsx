/**
 * Button — one component, four intents × three sizes.
 *
 * The system intentionally has only one Button so the rest of the app
 * can use a single import and a single set of opinions. Adding a new
 * variant should be a deliberate design change, not a per-page decision.
 */
import { type ButtonHTMLAttributes, type ReactNode } from "react";
import { Icon, type IconName } from "@/components/ui/icon";

type Variant = "primary" | "secondary" | "ghost" | "outline" | "danger" | "light";
type Size = "sm" | "md" | "lg";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  iconLeft?: IconName;
  iconRight?: IconName;
  loading?: boolean;
  fullWidth?: boolean;
  children?: ReactNode;
};

const base =
  "inline-flex items-center justify-center gap-2 rounded-full font-semibold " +
  "transition-all duration-200 hover:-translate-y-0.5 active:scale-95 " +
  "disabled:cursor-not-allowed disabled:opacity-60 disabled:translate-y-0 " +
  "disabled:active:scale-100 select-none whitespace-nowrap";

const variants: Record<Variant, string> = {
  primary:
    "bg-brand-700 text-white shadow-sm shadow-brand-900/20 " +
    "hover:bg-brand-800 active:bg-brand-900",
  secondary:
    "bg-surface text-ink-900 ring-1 ring-inset ring-ink-200 " +
    "hover:bg-ink-100 active:bg-ink-200/60",
  ghost: "text-ink-700 hover:bg-ink-100 active:bg-ink-200/60",
  outline:
    "bg-transparent text-brand-700 ring-1 ring-inset ring-brand-700/40 " +
    "hover:bg-brand-50 active:bg-brand-100",
  danger:
    "bg-rose-600 text-white shadow-sm shadow-rose-900/20 " +
    "hover:bg-rose-500 active:bg-rose-700",
  light:
    "bg-surface text-brand-900 ring-1 ring-inset ring-brand-100 " +
    "hover:bg-brand-50 active:bg-brand-100",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-4 text-sm",
  md: "h-11 px-5 text-sm",
  lg: "h-12 px-6 text-base",
};

const iconSize: Record<Size, string> = {
  sm: "h-4 w-4",
  md: "h-4 w-4",
  lg: "h-5 w-5",
};

export function Button({
  variant = "primary",
  size = "md",
  iconLeft,
  iconRight,
  loading = false,
  fullWidth = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={[
        base,
        variants[variant],
        sizes[size],
        fullWidth ? "w-full" : "",
        className,
      ].join(" ")}
    >
      {loading ? (
        <svg className={`${iconSize[size]} animate-spin`} viewBox="0 0 24 24" aria-hidden>
          <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
          <path d="M21 12a9 9 0 0 1-9 9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      ) : iconLeft ? (
        <Icon name={iconLeft} className={iconSize[size]} />
      ) : null}
      {children}
      {!loading && iconRight ? (
        <Icon name={iconRight} className={iconSize[size]} />
      ) : null}
    </button>
  );
}

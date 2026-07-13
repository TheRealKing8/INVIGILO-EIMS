/**
 * Form banner / status messages.
 *
 * Used by the auth pages to surface the "we sent you a link" /
 * "wrong password" / "session expired" states. Kept tiny on purpose:
 * status is a label, not a hero.
 */
import { type ReactNode } from "react";
import { Icon, type IconName } from "@/components/ui/icon";

type Tone = "info" | "success" | "warning" | "danger";

const toneClass: Record<Tone, string> = {
  info: "bg-sky-50 text-sky-800 ring-sky-200",
  success: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  warning: "bg-amber-50 text-amber-800 ring-amber-200",
  danger: "bg-rose-50 text-rose-800 ring-rose-200",
};

const toneIcon: Record<Tone, IconName> = {
  info: "sparkle",
  success: "check",
  warning: "alert",
  danger: "alert",
};

export function StatusBanner({
  tone = "info",
  title,
  children,
  actions,
}: {
  tone?: Tone;
  title: string;
  children?: ReactNode;
  /**
   * Optional right-aligned action area (typically a "Sign out" or
   * "Retry" button). Renders as a column on narrow viewports.
   */
  actions?: ReactNode;
}) {
  return (
    <div className={`flex items-start gap-3 rounded-2xl px-4 py-3 text-sm ring-1 ring-inset ${toneClass[tone]}`}>
      <Icon name={toneIcon[tone]} className="mt-0.5 h-4 w-4" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{title}</p>
        {children ? <p className="mt-0.5 text-sm opacity-90">{children}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

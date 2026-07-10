/**
 * Brand mark + lockup.
 *
 * Two variants:
 *   <BrandLockup size="md" /> — the full mark with wordmark
 *   <BrandMark size="md" />    — the icon-only glyph
 *
 * Sizes are designed so the glyph stays a perfect square and the
 * wordmark's cap height matches the glyph's height.
 */
import Link from "next/link";
import { Icon, type IconName } from "@/components/ui/icon";

type Size = "sm" | "md" | "lg" | "xl";

const sizeMap: Record<
  Size,
  { box: string; text: string; sub: string; iconSize: string }
> = {
  sm: { box: "h-8 w-8", text: "text-sm", sub: "text-[10px]", iconSize: "h-4 w-4" },
  md: { box: "h-10 w-10", text: "text-base", sub: "text-[11px]", iconSize: "h-5 w-5" },
  lg: { box: "h-12 w-12", text: "text-lg", sub: "text-xs", iconSize: "h-6 w-6" },
  xl: { box: "h-16 w-16", text: "text-2xl", sub: "text-sm", iconSize: "h-8 w-8" },
};

function Glyph({
  size,
  variant,
  iconName,
}: {
  size: Size;
  variant: "dark" | "light";
  iconName: IconName;
}) {
  const s = sizeMap[size];
  const bg = variant === "dark" ? "bg-brand-700" : "bg-white";
  const ring = variant === "dark" ? "ring-1 ring-white/10" : "ring-1 ring-brand-700/20";
  const color = variant === "dark" ? "text-white" : "text-brand-700";
  return (
    <div
      className={`relative flex ${s.box} items-center justify-center rounded-2xl ${bg} ${ring} shadow-sm shadow-brand-900/20`}
    >
      <span
        className={`absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-brand-400 ${variant === "dark" ? "" : ""} pulse-ring`}
        aria-hidden
      />
      <Icon name={iconName} className={`${s.iconSize} ${color}`} />
    </div>
  );
}

export function BrandMark({
  size = "md",
  variant = "dark",
  iconName = "shield",
}: {
  size?: Size;
  variant?: "dark" | "light";
  iconName?: IconName;
}) {
  return <Glyph size={size} variant={variant} iconName={iconName} />;
}

export function BrandLockup({
  size = "md",
  variant = "dark",
  href,
  iconName = "shield",
  showSubtitle = true,
}: {
  size?: Size;
  variant?: "dark" | "light";
  href?: string;
  iconName?: IconName;
  showSubtitle?: boolean;
}) {
  const s = sizeMap[size];
  const titleColor = variant === "dark" ? "text-white" : "text-brand-900";
  const subColor = variant === "dark" ? "text-brand-200/80" : "text-ink-500";

  const inner = (
    <div className="flex items-center gap-3">
      <Glyph size={size} variant={variant} iconName={iconName} />
      <div className="leading-none">
        <p className={`${s.text} font-semibold tracking-[0.22em] ${titleColor}`}>
          INVIGILO
        </p>
        {showSubtitle ? (
          <p className={`${s.sub} mt-1 font-medium tracking-wide ${subColor}`}>
            Examination operations
          </p>
        ) : null}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="inline-flex">
        {inner}
      </Link>
    );
  }
  return inner;
}

/**
 * Logo Strip — small, contextual social proof for the marketing page.
 *
 * Replaces the "live numbers" tile on the hero. The university logos
 * are abstracted into a wordmark row so the design doesn't depend on
 * third-party brand assets.
 */
const items = [
  { code: "UNI · NRB", name: "University of Nairobi" },
  { code: "KU", name: "Kenyatta University" },
  { code: "JKUAT", name: "Jomo Kenyatta University" },
  { code: "MU", name: "Moi University" },
  { code: "UOE", name: "University of Eldoret" },
  { code: "MMU", name: "Multimedia University" },
];

export function LogoStrip() {
  return (
    <div className="grid grid-cols-3 gap-x-6 gap-y-4 sm:grid-cols-6">
      {items.map((it) => (
        <div
          key={it.code}
          className="flex items-center gap-2 text-ink-500"
          title={it.name}
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 ring-1 ring-inset ring-brand-100 text-[10px] font-bold tracking-wider text-brand-700">
            {it.code}
          </span>
          <span className="hidden text-xs font-medium sm:block">{it.name}</span>
        </div>
      ))}
    </div>
  );
}

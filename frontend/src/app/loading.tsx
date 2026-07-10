/**
 * Route-level loading state.
 *
 * Renders while a dashboard route is fetching its server- or
 * client-side data. Matches the emerald/white design language
 * so the brief flicker between layout and page isn't jarring.
 */
export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex items-center gap-3 text-sm font-medium text-ink-500">
        <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500" />
        <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500 [animation-delay:120ms]" />
        <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500 [animation-delay:240ms]" />
        <span className="ml-2">Loading workspace…</span>
      </div>
    </div>
  );
}

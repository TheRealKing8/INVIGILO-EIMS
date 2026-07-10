"use client";

/**
 * Top-level error boundary.
 *
 * Caught by Next.js whenever a child segment throws during
 * rendering or data fetching. Stays in the design language
 * (emerald/white) and gives the user a "Try again" affordance
 * so they don't have to reload the page.
 */
import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("App error boundary caught:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md rounded-3xl bg-surface p-8 text-center shadow-[var(--shadow-card)] ring-1 ring-ink-200">
        <p className="eyebrow text-brand-700">Something went wrong</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink-900">
          We hit a snag rendering this view.
        </h1>
        <p className="mt-3 text-sm text-ink-700">
          {error.message || "An unexpected error occurred. You can try again, or head back to the dashboard."}
        </p>
        <div className="mt-6 flex items-center justify-center gap-2">
          <Button variant="primary" size="md" onClick={() => reset()}>
            Try again
          </Button>
          <Button variant="ghost" size="md" onClick={() => (window.location.href = "/dashboard")}>
            Go to dashboard
          </Button>
        </div>
        {error.digest ? (
          <p className="mt-4 text-[11px] uppercase tracking-[0.16em] text-ink-400">
            Reference {error.digest}
          </p>
        ) : null}
      </div>
    </div>
  );
}

/**
 * 404 — not found.
 *
 * Renders inside the root layout (no DashboardShell) so it's
 * reachable for any unknown route, including during development
 * when typing the wrong path into the URL bar.
 */
import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md rounded-3xl bg-surface p-8 text-center shadow-[var(--shadow-card)] ring-1 ring-ink-200">
        <p className="eyebrow text-brand-700">404</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink-900">
          We couldn't find that page.
        </h1>
        <p className="mt-3 text-sm text-ink-700">
          The link may be out of date, or the page may have been moved.
          Head back to the dashboard to keep working.
        </p>
        <div className="mt-6 flex items-center justify-center gap-2">
          <Link href="/dashboard">
            <Button variant="primary" size="md">Go to dashboard</Button>
          </Link>
          <Link href="/login">
            <Button variant="ghost" size="md">Sign in</Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

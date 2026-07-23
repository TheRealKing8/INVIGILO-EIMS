/**
 * Student landing — the "/dashboard/student" parent page.
 *
 * Phase 25. The sidebar surfaces this entry to STUDENT users (see
 * ``ROUTE_ACCESS`` in ``lib/route-config.ts``). It is the same
 * personalised overview that ``/dashboard`` already shows to a
 * STUDENT, but reachable directly via the sidebar link.
 *
 * For now this page is a thin pass-through to the dashboard home;
 * it exists so the static route map's ``/dashboard/student`` href
 * resolves to a real route. As the student surface grows (more
 * exam card pages, attendance history, etc.) this is where the
 * dedicated shell will live.
 */
"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * No-op rendering — immediately push the student to /dashboard,
 * which already has the STUDENT branch in ``StudentOverview``.
 * Keeping this as a router redirect (rather than a re-render of
 * the StudentOverview component) means the existing "Your next
 * exam" tile + the "View exam card" link stay in one place.
 */
export default function StudentLanding() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);
  return null;
}

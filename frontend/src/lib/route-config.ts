/**
 * Single source of truth for nav visibility and route access.
 *
 * Both ``DashboardNav`` (sidebar / mobile drawer) and the route guards
 * in ``lib/auth.tsx`` consume this map. Adding a new dashboard page
 * means: add a row here, add a Link in the page, done. The nav and
 * the route guard cannot drift apart because they read from the same
 * place.
 *
 * The role codes must match the backend (``apps.accounts.seed.ROLES``).
 * The server is still the source of truth for authorization — this
 * map is a UX layer that hides things the user cannot use and
 * redirects on direct-URL access. Every backend view still re-checks
 * ``HasPermission`` / ``IsRole`` independently.
 */
import type { IconName } from "@/components/ui/icon";

export type RoleCode =
  | "SYSTEM_ADMINISTRATOR"
  | "EXAMINATION_OFFICER"
  | "FACULTY_DEAN"
  | "HEAD_OF_DEPARTMENT"
  | "INVIGILATOR"
  | "SECURITY_OFFICER"
  | "STUDENT"
  | "GUEST";

/** A role that has access to any internal dashboard surface. */
export const DASHBOARD_ROLES: ReadonlySet<RoleCode> = new Set<RoleCode>([
  "SYSTEM_ADMINISTRATOR",
  "EXAMINATION_OFFICER",
  "FACULTY_DEAN",
  "HEAD_OF_DEPARTMENT",
  "INVIGILATOR",
  "SECURITY_OFFICER",
  "STUDENT",
  "GUEST",
]);

export type RouteAccess = {
  /** URL path, e.g. "/dashboard/exams". */
  href: string;
  /** Display label in the sidebar. */
  label: string;
  /** Short caption under the label. */
  description: string;
  /** Icon for the sidebar entry. */
  icon: IconName;
  /**
   * Roles that may both *see* this entry in the nav AND *open* the
   * route. The empty set means the entry is visible to every
   * authenticated user (e.g. the Overview page).
   */
  roles: ReadonlySet<RoleCode>;
};

/**
 * The order in this array is the order shown in the sidebar.
 * Keep the Overview row first — it's the safe landing page.
 */
export const ROUTE_ACCESS: ReadonlyArray<RouteAccess> = [
  {
    href: "/dashboard",
    label: "Overview",
    description: "Live operations snapshot",
    icon: "dashboard",
    // Every authenticated dashboard user sees the overview.
    roles: DASHBOARD_ROLES,
  },
  {
    href: "/dashboard/exams",
    label: "Examinations",
    description: "Schedule, rooms, sessions",
    icon: "calendar",
    roles: new Set<RoleCode>([
      "SYSTEM_ADMINISTRATOR",
      "EXAMINATION_OFFICER",
      "FACULTY_DEAN",
      "HEAD_OF_DEPARTMENT",
    ]),
  },
  {
    href: "/dashboard/timetable",
    label: "Timetable",
    description: "Day-by-day view of all sessions",
    icon: "calendar",
    // Every authenticated user can see the timetable; the backend
    // re-checks the data scope (e.g. students only see their own).
    roles: DASHBOARD_ROLES,
  },
  {
    href: "/dashboard/invigilators",
    label: "Invigilators",
    description: "Roster, availability, workload",
    icon: "users",
    roles: new Set<RoleCode>([
      "SYSTEM_ADMINISTRATOR",
      "EXAMINATION_OFFICER",
      "FACULTY_DEAN",
      "HEAD_OF_DEPARTMENT",
    ]),
  },
  {
    href: "/dashboard/allocations",
    label: "Allocations",
    description: "Smart engine, conflict check",
    icon: "lightning",
    roles: new Set<RoleCode>([
      "SYSTEM_ADMINISTRATOR",
      "EXAMINATION_OFFICER",
      "FACULTY_DEAN",
      "HEAD_OF_DEPARTMENT",
    ]),
  },
  {
    href: "/dashboard/incident",
    label: "Incidents",
    description: "Logs, escalations, resolution",
    icon: "alert",
    roles: new Set<RoleCode>([
      "SYSTEM_ADMINISTRATOR",
      "EXAMINATION_OFFICER",
      "FACULTY_DEAN",
      "HEAD_OF_DEPARTMENT",
      "INVIGILATOR",
      "SECURITY_OFFICER",
    ]),
  },
  {
    href: "/dashboard/reports",
    label: "Reports",
    description: "Daily, weekly, period exports",
    icon: "report",
    roles: new Set<RoleCode>([
      "SYSTEM_ADMINISTRATOR",
      "EXAMINATION_OFFICER",
      "FACULTY_DEAN",
      "HEAD_OF_DEPARTMENT",
    ]),
  },
  {
    href: "/dashboard/audit",
    label: "Audit log",
    description: "Who changed what, and when",
    icon: "shield",
    // Only roles that can see (and act on) consequential changes.
    // The backend independently re-checks ``audit.view``.
    roles: new Set<RoleCode>([
      "SYSTEM_ADMINISTRATOR",
      "EXAMINATION_OFFICER",
    ]),
  },
  {
    href: "/dashboard/attendance",
    label: "Attendance",
    description: "Check-ins, door roster, exports",
    icon: "check",
    // Secops runs the door roster, INVIGILATOR uses the self
    // check-in shortcut, the operations roles audit + export.
    // The backend re-checks ``attendance.view`` per action.
    roles: new Set<RoleCode>([
      "SYSTEM_ADMINISTRATOR",
      "EXAMINATION_OFFICER",
      "HEAD_OF_DEPARTMENT",
      "FACULTY_DEAN",
      "SECURITY_OFFICER",
      "INVIGILATOR",
    ]),
  },
  {
    href: "/dashboard/users",
    label: "Users",
    description: "All accounts, roles, password resets",
    icon: "users",
    // Backend independently re-checks ``accounts.user.create`` (for
    // list/create/update) and the two elevated actions
    // ``accounts.user.reset_password`` / ``accounts.role.assign`` (for
    // the detail page). The route config is the UX layer that hides
    // the entry for everyone except the SA.
    roles: new Set<RoleCode>(["SYSTEM_ADMINISTRATOR"]),
  },
];

/**
 * True for roles that operate the platform — the dashboard's
 * "control-room" branch shows them the full org-wide KPIs. Everyone
 * else (INVIGILATOR, SECURITY_OFFICER, STUDENT, GUEST) gets a
 * role-specific slice.
 */
export function isOperationsRole(code: string | null | undefined): boolean {
  return (
    code === "SYSTEM_ADMINISTRATOR" ||
    code === "EXAMINATION_OFFICER" ||
    code === "HEAD_OF_DEPARTMENT" ||
    code === "FACULTY_DEAN"
  );
}

/** True if the user (by primary role) may access this exact route. */
export function canAccessRoute(
  primaryRole: string | null | undefined,
  href: string,
): boolean {
  const role = (primaryRole ?? "") as RoleCode | "";
  const entry = ROUTE_ACCESS.find((r) => r.href === href);
  if (!entry) return false;
  return entry.roles.has(role as RoleCode);
}

/**
 * Return the nav entries the user is allowed to see, in declaration
 * order. Used by Sidebar and MobileNav.
 */
export function visibleNavItems(
  primaryRole: string | null | undefined,
): RouteAccess[] {
  const role = (primaryRole ?? "") as RoleCode | "";
  return ROUTE_ACCESS.filter((r) => r.roles.has(role as RoleCode));
}

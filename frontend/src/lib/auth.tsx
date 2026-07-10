/**
 * Client-side auth context and route guards.
 *
 * ``useAuth()`` returns the currently-stored ``AuthUser`` (or null if
 * the user is signed out). The value updates whenever the storage
 * fires a ``storage`` event (cross-tab logout) or any code in this tab
 * calls ``notifyAuthChange()`` after a login / logout / refresh.
 *
 * The route guards (``<RequireRole>`` and ``<RequirePermission>``) are
 * thin wrappers around this hook. They render ``children`` only when
 * the user is allowed; on deny, they redirect to ``/dashboard``.
 *
 * The server is still the source of truth for authorization. This
 * file is a UX layer — it hides things the user cannot use, and
 * keeps the URL bar in sync when a user types a forbidden path
 * directly. Every backend view still re-checks ``HasPermission`` /
 * ``IsRole`` independently.
 */
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";

import {
  getStoredUser,
  type AuthUser,
} from "@/lib/api";
import {
  DASHBOARD_ROLES,
  ROUTE_ACCESS,
  canAccessRoute,
  type RoleCode,
} from "@/lib/route-config";

// ---------------------------------------------------------------------------
// Auth state — useSyncExternalStore against localStorage
// ---------------------------------------------------------------------------
/**
 * useSyncExternalStore wants the same value identity across calls when
 * nothing has changed, otherwise it re-renders needlessly. We cache the
 * last parsed user on a module-level variable and return the same
 * object reference until localStorage changes.
 */
let cachedUser: AuthUser | null | undefined = undefined;

function readUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  // Re-parse on every call so the cache is fresh — but the test
  // (referential equality) below decides whether subscribers re-render.
  const next = getStoredUser();
  if (
    cachedUser === undefined ||
    !sameUserRef(cachedUser, next)
  ) {
    cachedUser = next;
  }
  return cachedUser;
}

function sameUserRef(a: AuthUser | null, b: AuthUser | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  // Cheap identity check: if the id and role match, the server hasn't
  // reassigned anything important and we can return the previous
  // object reference. This keeps useSyncExternalStore from re-running
  // its reducer.
  return a.id === b.id && a.primary_role === b.primary_role;
}

const AUTH_CHANGE_EVENT = "invigilo:auth-change";

function subscribeAuth(notify: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const onChange = () => {
    // Force the snapshot to re-evaluate on the next render.
    cachedUser = undefined;
    notify();
  };
  window.addEventListener("storage", notify);
  window.addEventListener(AUTH_CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener(AUTH_CHANGE_EVENT, onChange);
  };
}

function getServerSnapshot(): AuthUser | null {
  // The server has no localStorage. Returning a stable null lets the
  // client hydrate to the real value without a mismatch.
  return null;
}

function getClientSnapshot(): AuthUser | null {
  return readUser();
}

function emitAuthChange(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

/**
 * Call this from anywhere in the client tree after writing auth state
 * (``saveAuthTokens``, ``clearAuthTokens``) so subscribed components
 * re-render with the new value. Safe to call multiple times.
 */
export function notifyAuthChange(): void {
  emitAuthChange();
}

type AuthContextValue = {
  user: AuthUser | null;
  /**
   * True once the provider has mounted and the client-side snapshot is
   * trustworthy. Route guards gate on this to avoid redirecting on
   * the first render (which would always be ``null`` on the server).
   */
  isReady: boolean;
  /** Re-read localStorage and re-render. Call after login / logout. */
  refresh: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // useSyncExternalStore is the React 19-recommended way to read
  // external mutable state. It handles SSR/hydration correctly out of
  // the box — the server returns the server snapshot, the client
  // returns the client snapshot, no manual ``isReady`` flag needed.
  const user = useSyncExternalStore(subscribeAuth, getClientSnapshot, getServerSnapshot);

  // "isReady" — true on the client, false on the server. This is the
  // canonical React 19 idiom for "did we hydrate?" without a
  // setState-in-effect. The subscribe function is a no-op (nothing
  // to listen to), but the snapshot differs between server (false)
  // and client (true) so the hook reports the right value.
  const isReady = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );

  const refresh = useCallback(() => {
    cachedUser = undefined;
    notifyAuthChange();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isReady, refresh }),
    [user, isReady, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    // Useful when a guard is rendered outside <AuthProvider> (e.g. in a
    // test). Falling back to a direct read is correct, just not reactive.
    return {
      user: getStoredUser(),
      isReady: typeof window !== "undefined",
      refresh: () => undefined,
    };
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// Pure predicates (no React) — exported for use in server-rendered paths
// and in tests.
// ---------------------------------------------------------------------------
export function hasRole(
  user: AuthUser | null,
  ...codes: RoleCode[]
): boolean {
  if (!user) return false;
  const role = (user.primary_role ?? user.role ?? "") as RoleCode | "";
  if (!role) return false;
  return codes.includes(role);
}

export function hasAnyRole(
  user: AuthUser | null,
  codes: ReadonlySet<RoleCode>,
): boolean {
  if (!user) return false;
  const role = user.primary_role ?? user.role ?? "";
  if (!role) return false;
  return codes.has(role as RoleCode);
}

export function hasPermission(
  user: AuthUser | null,
  code: string,
): boolean {
  if (!user) return false;
  if (user.is_staff) return true; // Mirror server: superuser/staff bypass.
  const perms = user.permissions ?? [];
  return perms.includes(code);
}

export function hasAllPermissions(
  user: AuthUser | null,
  codes: string[],
): boolean {
  if (!user) return false;
  if (user.is_staff) return true;
  const perms = new Set(user.permissions ?? []);
  return codes.every((c) => perms.has(c));
}

// ---------------------------------------------------------------------------
// Route guards
// ---------------------------------------------------------------------------
type RedirectTarget = string;

function redirectTo(router: ReturnType<typeof useRouter>, target: RedirectTarget) {
  // Defer to a microtask so the redirect runs after the current render
  // commit; otherwise React 19 logs a warning about state updates
  // during render.
  queueMicrotask(() => router.replace(target));
}

export function RequireRole({
  roles,
  children,
  fallbackHref = "/dashboard",
}: {
  roles: ReadonlySet<RoleCode>;
  children: ReactNode;
  fallbackHref?: string;
}) {
  const { user, isReady } = useAuth();
  const router = useRouter();

  const allowed = isReady ? hasAnyRole(user, roles) : true;
  useEffect(() => {
    if (isReady && !allowed) redirectTo(router, fallbackHref);
  }, [isReady, allowed, router, fallbackHref]);

  if (!allowed) return null;
  return <>{children}</>;
}

/**
 * Gate a sub-tree on the current pathname. When the user is not
 * allowed to access the page they're on, redirect to the fallback.
 *
 * Usage in a page::
 *
 *     export default function Page() {
 *       return (
 *         <RequireRoute>
 *           <DashboardShell ...>...</DashboardShell>
 *         </RequireRoute>
 *       );
 *     }
 */
export function RequireRoute({
  children,
  fallbackHref = "/dashboard",
}: {
  children: ReactNode;
  fallbackHref?: string;
}) {
  const { user, isReady } = useAuth();
  const router = useRouter();
  // Next.js's usePathname is reactive and returns the current path
  // on the client (null on the server). Combined with the auth
  // context's ``isReady`` flag, we can defer the route check until
  // we actually have both pieces of information.
  const pathname = usePathname();

  // Don't evaluate the route check until BOTH the auth context is
  // ready (i.e. localStorage was read) AND we know the current path.
  // Otherwise a reload straight onto a forbidden URL would flash a
  // redirect before the user is identified.
  const allowed =
    isReady && pathname
      ? canAccessRoute(user?.primary_role ?? user?.role, pathname)
      : true;

  useEffect(() => {
    if (isReady && pathname && !allowed) redirectTo(router, fallbackHref);
  }, [isReady, pathname, allowed, router, fallbackHref]);

  if (!allowed) return null;
  return <>{children}</>;
}

/**
 * Gate the entire ``/dashboard`` subtree on the user being a member
 * of the dashboard user set. If they're not, send them to the
 * landing page. This is the dashboard equivalent of a route group
 * guard.
 */
export function RequireDashboardRole({
  children,
  fallbackHref = "/",
}: {
  children: ReactNode;
  fallbackHref?: string;
}) {
  const { user, isReady } = useAuth();
  const router = useRouter();
  const allowed = isReady ? hasAnyRole(user, DASHBOARD_ROLES) : true;

  useEffect(() => {
    if (isReady && !allowed) redirectTo(router, fallbackHref);
  }, [isReady, allowed, router, fallbackHref]);

  if (!allowed) return null;
  return <>{children}</>;
}

export function RequirePermission({
  codes,
  children,
  fallbackHref = "/dashboard",
  requireAll = true,
}: {
  codes: string[];
  children: ReactNode;
  fallbackHref?: string;
  requireAll?: boolean;
}) {
  const { user, isReady } = useAuth();
  const router = useRouter();

  const allowed = isReady
    ? requireAll
      ? hasAllPermissions(user, codes)
      : (user?.permissions ?? []).some((c) => codes.includes(c))
    : true;

  useEffect(() => {
    if (isReady && !allowed) redirectTo(router, fallbackHref);
  }, [isReady, allowed, router, fallbackHref]);

  if (!allowed) return null;
  return <>{children}</>;
}

// Re-export the route map so consumers don't need a second import.
export { ROUTE_ACCESS };

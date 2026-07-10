"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { clearAuthTokens, getProfile, getStoredAccessToken, getStoredRefreshToken, logoutRequest } from "@/lib/api";
import { notifyAuthChange, useAuth } from "@/lib/auth";
import { MobileNav, Sidebar, Topbar } from "@/components/ui/dashboard-nav";
import { RequireRoute } from "@/lib/auth";

type DashboardShellProps = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
};

export function DashboardShell({ title, subtitle, actions, children }: DashboardShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);
  const { user, refresh: refreshAuth } = useAuth();

  useEffect(() => {
    const accessToken = getStoredAccessToken();
    if (!accessToken) {
      clearAuthTokens();
      notifyAuthChange();
      router.replace("/login");
      return;
    }

    // The context already has the cached user from localStorage; only
    // re-fetch the profile when the access token is fresh. After the
    // fetch, push the up-to-date user (with permissions) into the
    // shared auth context so route guards see the right state.
    getProfile(accessToken)
      .then((profile) => {
        refreshAuth();
        // Persist any newly-fetched fields back to storage so a
        // subsequent reload doesn't re-fetch.
        const stored = {
          id: profile.id,
          email: profile.email,
          full_name: profile.full_name,
          primary_role: profile.primary_role,
          role: profile.role,
          permissions: profile.permissions,
          is_email_verified: profile.is_email_verified,
          is_staff: profile.is_staff,
        };
        // saveAuthTokens also writes tokens; we re-use it to update
        // the user object. The existing tokens are still valid for
        // this request lifetime, but the access token may need a
        // refresh; the 401 handler in api.ts will take care of that.
        if (typeof window !== "undefined") {
          localStorage.setItem("invigilo_user", JSON.stringify(stored));
          notifyAuthChange();
        }
      })
      .catch(() => {
        clearAuthTokens();
        notifyAuthChange();
        router.replace("/login");
      })
      .finally(() => setIsReady(true));
    // We intentionally only run this on mount; subsequent navigation
    // doesn't need a fresh profile.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function handleSignOut() {
    const refresh = getStoredRefreshToken();
    if (refresh) {
      try {
        await logoutRequest(refresh);
      } catch {
        // best-effort; clear locally regardless
      }
    }
    clearAuthTokens();
    notifyAuthChange();
    router.replace("/login");
  }

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-sm font-medium text-ink-500">
          <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500" />
          <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500 [animation-delay:120ms]" />
          <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500 [animation-delay:240ms]" />
          <span className="ml-2">Verifying your session…</span>
        </div>
      </div>
    );
  }

  return (
    <RequireRoute>
      <div className="flex min-h-screen bg-background text-ink-900">
        <Sidebar pathname={pathname} user={user} onSignOut={handleSignOut} />
        <div className="flex min-w-0 flex-1 flex-col">
          <MobileNav pathname={pathname} user={user} onSignOut={handleSignOut} />
          <Topbar
            user={user}
            onSignOut={handleSignOut}
            title={title}
            subtitle={subtitle}
            actions={actions}
          />
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
        </div>
      </div>
    </RequireRoute>
  );
}

/**
 * User detail — admin-only management of a single account.
 *
 * The page composes three cards (Profile, Reset password, Roles)
 * plus a footer row for the disable / unlock actions. Each card
 * has its own submit; the page refetches the user on success so the
 * UI stays in sync.
 *
 * The "Save roles" button is hidden when the proposed change would
 * leave the current admin with no admin role — the same lockout
 * guard the backend applies via the codename checks, surfaced in
 * the UI so the admin doesn't strand themselves.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  adminResetUserPassword,
  deleteUser,
  getUser,
  setUserRoles,
  unlockUserAccount,
  type User,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isOperationsRole } from "@/lib/route-config";
import { useFetch } from "@/lib/use-fetch";
import {
  isValidPassword,
  passwordMatches,
} from "@/lib/validation";

const ALL_ROLES = [
  { code: "SYSTEM_ADMINISTRATOR", label: "System Administrator" },
  { code: "EXAMINATION_OFFICER", label: "Examination Officer" },
  { code: "HEAD_OF_DEPARTMENT", label: "Head of Department" },
  { code: "FACULTY_DEAN", label: "Faculty Dean" },
  { code: "INVIGILATOR", label: "Invigilator" },
  { code: "SECURITY_OFFICER", label: "Security Officer" },
  { code: "STUDENT", label: "Student" },
  { code: "GUEST", label: "Guest" },
] as const;

type ResetState = {
  newPassword: string;
  confirmPassword: string;
  submitting: boolean;
  error: string | null;
  success: string | null;
};

const EMPTY_RESET: ResetState = {
  newPassword: "",
  confirmPassword: "",
  submitting: false,
  error: null,
  success: null,
};

export default function UserDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const router = useRouter();
  const { user: me } = useAuth();
  const isSelf = me?.id === id;

  const { data: user, isLoading, error, refresh } = useFetch(() => getUser(id), [id]);

  // Track the in-flight role set locally so the checkboxes reflect
  // optimistic state until the next refresh lands.
  const [roleDraft, setRoleDraft] = useState<Set<string> | null>(null);
  useEffect(() => {
    if (user) setRoleDraft(new Set(user.roles.map((r) => r.code)));
  }, [user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const [rolesSubmitting, setRolesSubmitting] = useState(false);
  const [rolesError, setRolesError] = useState<string | null>(null);
  const [resetState, setResetState] = useState<ResetState>(EMPTY_RESET);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionInfo, setActionInfo] = useState<string | null>(null);

  const isLocked = useMemo(
    () => !!(user?.locked_until && new Date(user.locked_until).getTime() > Date.now()),
    [user?.locked_until],
  );

  // ---- Derived UI bits ----------------------------------------------
  // The role set the admin is about to save (or null = not yet edited).
  const dirtyRoles = useMemo(() => {
    if (!user || !roleDraft) {
      return { added: [] as string[], removed: [] as string[] };
    }
    const original = new Set(user.roles.map((r) => r.code));
    const added: string[] = [];
    const removed: string[] = [];
    for (const r of roleDraft) if (!original.has(r)) added.push(r);
    for (const r of original) if (!roleDraft.has(r)) removed.push(r);
    return { added, removed };
  }, [user, roleDraft]);

  const wouldLockOutSelf = useMemo(() => {
    if (!isSelf || !user || !roleDraft) return false;
    const hadAdmin =
      user.roles.some((r) => r.code === "SYSTEM_ADMINISTRATOR") || !!user.is_superuser;
    if (!hadAdmin) return false;
    // The admin is keeping the SYSTEM_ADMINISTRATOR role (or is a
    // superuser, which can't be revoked by this UI).
    return !roleDraft.has("SYSTEM_ADMINISTRATOR") && !user.is_superuser;
  }, [isSelf, user, roleDraft]);

  // ---- Handlers -----------------------------------------------------
  async function handleReset(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setResetState((s) => ({ ...s, error: null, success: null }));
    const pwd = resetState.newPassword;
    const pwdCheck = isValidPassword(pwd);
    if (!pwdCheck.ok) {
      setResetState((s) => ({ ...s, error: pwdCheck.message }));
      return;
    }
    if (!passwordMatches(pwd, resetState.confirmPassword)) {
      setResetState((s) => ({ ...s, error: "Passwords do not match." }));
      return;
    }
    setResetState((s) => ({ ...s, submitting: true }));
    try {
      await adminResetUserPassword(id, pwd, resetState.confirmPassword);
      setResetState({
        newPassword: "",
        confirmPassword: "",
        submitting: false,
        error: null,
        success: "Password reset. The user must sign in again with the new password.",
      });
    } catch (err) {
      setResetState((s) => ({
        ...s,
        submitting: false,
        error: err instanceof Error ? err.message : "Could not reset the password.",
      }));
    }
  }

  async function handleSaveRoles() {
    if (!roleDraft) return;
    setRolesError(null);
    setRolesSubmitting(true);
    try {
      await setUserRoles(id, Array.from(roleDraft));
      await refresh();
    } catch (err) {
      setRolesError(err instanceof Error ? err.message : "Could not save roles.");
    } finally {
      setRolesSubmitting(false);
    }
  }

  async function handleDisable() {
    if (!user) return;
    if (
      !window.confirm(
        `Disable ${user.email}? They will no longer be able to sign in. You can re-enable from this page.`,
      )
    ) {
      return;
    }
    setActionError(null);
    setActionInfo(null);
    try {
      await deleteUser(id);
      setActionInfo("User disabled.");
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not disable the user.");
    }
  }

  async function handleUnlock() {
    setActionError(null);
    setActionInfo(null);
    try {
      await unlockUserAccount(id);
      setActionInfo("User unlocked. Failed-login counter cleared.");
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not unlock the user.");
    }
  }

  // ---- Render -------------------------------------------------------
  if (isLoading) {
    return (
      <DashboardShell title="Loading user" subtitle="">
        <StatusBanner tone="info" title="Loading…">
          Fetching user details.
        </StatusBanner>
      </DashboardShell>
    );
  }

  if (error || !user) {
    return (
      <DashboardShell
        title="User not found"
        subtitle="The user may have been deleted or you may not have permission to view it."
        actions={
          <Link href="/dashboard/users">
            <Button variant="ghost" size="md" iconLeft="arrow-left">
              Back to users
            </Button>
          </Link>
        }
      >
        <StatusBanner tone="danger" title="Could not load this user">
          {error?.message ?? "User not found."}
        </StatusBanner>
      </DashboardShell>
    );
  }

  const dirty = !isSelf || !wouldLockOutSelf;

  return (
    <DashboardShell
      title={user.full_name || user.email}
      subtitle={user.email}
      actions={
        <Link href="/dashboard/users">
          <Button variant="ghost" size="md" iconLeft="arrow-left">
            Back to users
          </Button>
        </Link>
      }
    >
      {/* ---- Profile card --------------------------------------- */}
      <Card>
        <CardHeader
          eyebrow="Profile"
          title="Account details"
          subtitle="Read-only summary of the user's record."
        />
        <div className="mt-5 grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Email" value={user.email} />
          <Field label="Full name" value={user.full_name || "—"} />
          <Field label="Phone" value={user.phone || "—"} />
          <Field label="Time zone" value={user.time_zone || "—"} />
          <Field
            label="Status"
            value={
              user.is_active
                ? isLocked
                  ? "Active (locked)"
                  : "Active"
                : "Disabled"
            }
          />
          <Field
            label="Email verified"
            value={user.is_email_verified ? "Yes" : "No"}
          />
          <Field label="Last sign-in" value={formatDate(user.last_login_at)} />
          <Field
            label="Failed sign-ins"
            value={String(user.failed_login_count)}
          />
          <Field
            label="Locked until"
            value={user.locked_until ? formatDate(user.locked_until) : "—"}
          />
          <Field label="Created" value={formatDate(user.created_at)} />
          <Field label="Updated" value={formatDate(user.updated_at)} />
        </div>
      </Card>

      {/* ---- Roles card ---------------------------------------- */}
      <Card className="mt-6">
        <CardHeader
          eyebrow="Roles"
          title="Assign roles"
          subtitle="Replace the user's full role set. Unknown role codes are rejected by the server."
        />

        {isSelf && wouldLockOutSelf ? (
          <div className="mt-5">
            <StatusBanner tone="warning" title="This would lock you out">
              You're signed in as this user. Removing the SYSTEM_ADMINISTRATOR role
              would prevent you from signing in again. Cancel the change or keep at
              least one admin role on this account.
            </StatusBanner>
          </div>
        ) : null}

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {ALL_ROLES.map((r) => {
            const checked = roleDraft?.has(r.code) ?? false;
            return (
              <label
                key={r.code}
                className="flex items-center gap-3 rounded-2xl bg-ink-100/40 px-4 py-3 ring-1 ring-inset ring-ink-200 transition hover:bg-ink-100/70"
              >
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
                  checked={checked}
                  onChange={(e) => {
                    setRoleDraft((prev) => {
                      const next = new Set(prev ?? []);
                      if (e.target.checked) next.add(r.code);
                      else next.delete(r.code);
                      return next;
                    });
                  }}
                />
                <span className="text-sm font-medium text-ink-800">{r.label}</span>
                <span className="ml-auto text-xs text-ink-500">{r.code}</span>
              </label>
            );
          })}
        </div>

        {rolesError ? (
          <div className="mt-4">
            <StatusBanner tone="danger" title="Could not save roles">
              {rolesError}
            </StatusBanner>
          </div>
        ) : null}

        <div className="mt-5 flex items-center justify-between border-t border-ink-100 pt-5">
          <p className="text-xs text-ink-500">
            {dirtyRoles.added.length + dirtyRoles.removed.length === 0
              ? "No changes yet."
              : `${dirtyRoles.added.length} added · ${dirtyRoles.removed.length} removed`}
          </p>
          <Button
            variant="primary"
            size="md"
            iconLeft="check"
            disabled={
              !dirty ||
              rolesSubmitting ||
              dirtyRoles.added.length + dirtyRoles.removed.length === 0
            }
            loading={rolesSubmitting}
            onClick={() => void handleSaveRoles()}
          >
            Save roles
          </Button>
        </div>
      </Card>

      {/* ---- Reset password card ------------------------------ */}
      <Card className="mt-6">
        <CardHeader
          eyebrow="Security"
          title="Reset password"
          subtitle="Set a new password for this account. The user must sign in again with the new password."
        />

        {isSelf ? (
          <div className="mt-5">
            <StatusBanner tone="info" title="That's you">
              You're signed in as this user. Resetting your own password is allowed,
              but you'll be signed out and will need to use the new password to
              sign in again.
            </StatusBanner>
          </div>
        ) : null}

        <form className="mt-5 space-y-4" onSubmit={handleReset}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="New password"
              name="new_password"
              type="password"
              autoComplete="new-password"
              iconLeft="shield"
              value={resetState.newPassword}
              onChange={(e) =>
                setResetState((s) => ({ ...s, newPassword: e.target.value }))
              }
              hint="At least 12 chars · 3 of 4 classes (lower/upper/digit/symbol) · not a common password"
            />
            <Input
              label="Confirm password"
              name="confirm_password"
              type="password"
              autoComplete="new-password"
              iconLeft="shield"
              value={resetState.confirmPassword}
              onChange={(e) =>
                setResetState((s) => ({ ...s, confirmPassword: e.target.value }))
              }
            />
          </div>

          {resetState.error ? (
            <StatusBanner tone="danger" title="Could not reset password">
              {resetState.error}
            </StatusBanner>
          ) : null}
          {resetState.success ? (
            <StatusBanner tone="success" title="Password updated">
              {resetState.success}
            </StatusBanner>
          ) : null}

          <div className="flex items-center justify-end border-t border-ink-100 pt-5">
            <Button
              type="submit"
              variant="primary"
              size="md"
              iconLeft="shield"
              loading={resetState.submitting}
              disabled={
                resetState.submitting ||
                !resetState.newPassword ||
                !resetState.confirmPassword
              }
            >
              {resetState.submitting ? "Resetting…" : "Reset password"}
            </Button>
          </div>
        </form>
      </Card>

      {/* ---- Status actions ----------------------------------- */}
      <Card className="mt-6">
        <CardHeader
          eyebrow="Status"
          title="Account state"
          subtitle="Disable to prevent sign-in (soft-delete). Unlock to clear a 5-failure lockout."
        />

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Badge tone={user.is_active ? "success" : "neutral"} withDot>
            {user.is_active ? "Active" : "Disabled"}
          </Badge>
          {isLocked ? (
            <Badge tone="warning" withDot>
              Locked
            </Badge>
          ) : null}
          {user.is_superuser ? <Badge tone="info">Superuser</Badge> : null}
          {user.is_staff ? <Badge tone="info">Staff</Badge> : null}
          {isSelf ? <Badge tone="brand">This is you</Badge> : null}
        </div>

        {actionError ? (
          <div className="mt-4">
            <StatusBanner tone="danger" title="Action failed">
              {actionError}
            </StatusBanner>
          </div>
        ) : null}
        {actionInfo ? (
          <div className="mt-4">
            <StatusBanner tone="success" title="Done">
              {actionInfo}
            </StatusBanner>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-3 border-t border-ink-100 pt-5">
          {isLocked ? (
            <Button
              variant="primary"
              size="md"
              iconLeft="check"
              onClick={() => void handleUnlock()}
            >
              Unlock account
            </Button>
          ) : null}
          {user.is_active ? (
            <Button
              variant="ghost"
              size="md"
              iconLeft="lock"
              onClick={() => void handleDisable()}
              disabled={isSelf}
            >
              Disable account
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="md"
              iconLeft="refresh"
              onClick={async () => {
                // Re-enabling is intentionally not a separate endpoint
                // — admin resets the password and the user signs in
                // fresh, which brings is_active back via the create
                // path. We surface the "Enable" path here as a
                // pointer to the password-reset card.
                router.refresh();
              }}
            >
              How do I re-enable?
            </Button>
          )}
        </div>

        {isSelf ? (
          <p className="mt-3 text-xs text-ink-500">
            You can't disable your own account — ask another admin.
          </p>
        ) : null}
      </Card>

      {/* Footer note explaining the codenames used here. */}
      <p className="mt-6 text-center text-xs text-ink-500">
        Profile read by <code>accounts.user.create</code> · password reset by{" "}
        <code>accounts.user.reset_password</code> · roles by <code>accounts.role.assign</code>
        {isOperationsRole(me?.primary_role ?? me?.role) ? null : (
          <> · some actions are SA-only</>
        )}
      </p>
    </DashboardShell>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-ink-500">{label}</p>
      <p className="mt-0.5 text-sm font-medium text-ink-900">{value}</p>
    </div>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

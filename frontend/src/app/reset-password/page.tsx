/**
 * Password-reset confirm — the page the email link opens.
 *
 * The user lands here from the link in their "Reset your password"
 * email. The link carries a single-use token as ``?token=…``; we
 * forward that token to ``POST /api/v1/auth/password/reset/confirm/``
 * along with their new password. On success we swap the form for a
 * success banner + a CTA back to /login. On any 4xx/5xx we surface
 * the server's message in the top-of-form ``StatusBanner`` and leave
 * the form in place so they can try again.
 *
 * Field-level validation is shared with the register page
 * (``lib/validation.ts``), so the rules the user sees here are
 * exactly the rules the server enforces — see
 * ``backend/apps/accounts/validators.py``.
 */
"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { PasswordField } from "@/components/password-field";
import { Button } from "@/components/ui/button";
import { StatusBanner } from "@/components/ui/status-banner";
import { Icon } from "@/components/ui/icon";
import { confirmPasswordReset } from "@/lib/api";
import { validateRegister } from "@/lib/validation";

export default function ResetPasswordPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  // Field-level client errors.
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmPasswordError, setConfirmPasswordError] = useState<string | null>(null);
  // Top-of-form banner for server errors (token expired, weak password rejected, etc).
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  // Reuse the register-page validator. ``fullName`` and ``email`` are
  // blank here, but the validator returns null for blank fields it
  // doesn't care about — only ``password`` and ``confirmPassword``
  // are reported. We re-run it on every keystroke.
  const validation = useMemo(
    () => validateRegister("", "", newPassword, confirmPassword),
    [newPassword, confirmPassword],
  );

  function clearError(field: "password" | "confirm") {
    if (field === "password" && passwordError) setPasswordError(null);
    if (field === "confirm" && confirmPasswordError) setConfirmPasswordError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitAttempted(true);
    setServerError(null);

    const v = validateRegister("", "", newPassword, confirmPassword);
    setPasswordError(v.password);
    setConfirmPasswordError(v.confirmPassword);
    if (!v.isValid) {
      return;
    }

    if (!token) {
      // Should not happen — the form is only rendered when a token is
      // present (see the early return below) — but be defensive.
      setServerError(
        "This reset link is missing a token. Request a fresh link from the forgot-password page.",
      );
      return;
    }

    setIsSubmitting(true);
    try {
      await confirmPasswordReset(token, newPassword);
      setIsComplete(true);
    } catch (err) {
      setServerError(
        err instanceof Error
          ? err.message
          : "We couldn't reset your password. The link may have expired — try requesting a new one.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  // Only show inline errors after the first submit attempt. Same
  // pattern as the register page — keeps the form quiet on first
  // paint and reactive on the second click.
  const showPasswordError = submitAttempted ? passwordError : null;
  const showConfirmError = submitAttempted ? confirmPasswordError : null;

  // No token in URL — render a "go request a new link" panel.
  if (!token) {
    return (
      <AuthShell
        title="Reset link is missing a token"
        subtitle="Open the link directly from your reset email. If you closed the email by mistake, you can request a new one below."
        altLink={{ href: "/login", label: "Back to sign in" }}
        hero={{
          eyebrow: "Step 2 of 2 — Account recovery",
          headline: "Almost there.",
        }}
      >
        <div className="space-y-5">
          <StatusBanner tone="warning" title="No reset token in the URL">
            The reset link in your email is the only way to set a new password.
            If you bookmarked this page, request a fresh link instead.
          </StatusBanner>
          <Button
            type="button"
            size="lg"
            fullWidth
            onClick={() => router.push("/forgot-password")}
            iconRight="arrow-right"
          >
            Request a new reset link
          </Button>
        </div>
      </AuthShell>
    );
  }

  // Success state — banner + back-to-sign-in CTA.
  if (isComplete) {
    return (
      <AuthShell
        title="Your password has been reset"
        subtitle="You can sign in now with your new password. All your previous sessions have been signed out."
        altLink={{ href: "/login", label: "Back to sign in" }}
        hero={{
          eyebrow: "Step 2 of 2 — Account recovery",
          headline: "You're back in control.",
        }}
      >
        <div className="space-y-5">
          <StatusBanner tone="success" title="Password updated">
            Your new password is active. Sign in to continue.
          </StatusBanner>
          <Link
            href="/login"
            className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-full bg-brand-700 px-6 text-base font-semibold text-white shadow-sm shadow-brand-900/20 transition hover:bg-brand-800"
          >
            <Icon name="arrow-right" className="h-5 w-5" />
            Continue to sign in
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Choose a new password"
      subtitle="Pick something strong — 6+ characters mixing at least three of: lowercase, uppercase, digit, symbol. All your other sessions will be signed out."
      altLink={{ href: "/login", label: "Back to sign in" }}
      hero={{
        eyebrow: "Step 2 of 2 — Account recovery",
        headline: "Set a new password.",
      }}
    >
      <form className="space-y-5" onSubmit={handleSubmit} noValidate>
        {serverError ? (
          <StatusBanner tone="danger" title="We couldn't reset your password">
            {serverError}
          </StatusBanner>
        ) : null}

        <PasswordField
          id="newPassword"
          label="New password"
          value={newPassword}
          onChange={(e) => {
            setNewPassword(e.target.value);
            clearError("password");
            if (serverError) setServerError(null);
          }}
          required
          autoComplete="new-password"
          hint="6+ characters, mixing at least three of: lowercase, uppercase, digit, symbol."
          error={showPasswordError ?? undefined}
        />

        <PasswordField
          id="confirmPassword"
          label="Confirm new password"
          value={confirmPassword}
          onChange={(e) => {
            setConfirmPassword(e.target.value);
            clearError("confirm");
            if (serverError) setServerError(null);
          }}
          required
          autoComplete="new-password"
          error={showConfirmError ?? undefined}
        />

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={isSubmitting}
          disabled={submitAttempted && !validation.isValid}
          iconRight={isSubmitting ? undefined : "check"}
        >
          {isSubmitting ? "Resetting your password…" : "Reset password"}
        </Button>

        <div className="flex items-center gap-3 rounded-2xl bg-ink-100 p-3 text-xs text-ink-700 ring-1 ring-inset ring-ink-200">
          <Icon name="shield" className="h-4 w-4 text-ink-500" />
          <span>
            After the reset you'll be signed out of every other device. Sign in
            again with your new password to pick up where you left off.
          </span>
        </div>
      </form>
    </AuthShell>
  );
}

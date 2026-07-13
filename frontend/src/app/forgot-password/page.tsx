/**
 * Forgot-password — Step 1 of the account-recovery flow.
 *
 * The user enters their email, we POST to
 * ``/api/v1/auth/password/reset/``, and we always render a success
 * banner regardless of whether the email is registered (the API
 * returns 202 either way to prevent user-enumeration). The reset
 * link in the resulting email opens ``/reset-password?token=…``.
 */
"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBanner } from "@/components/ui/status-banner";
import { requestPasswordReset } from "@/lib/api";
import { isValidEmail } from "@/lib/validation";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitAttempted, setSubmitAttempted] = useState(false);

  // Run the email validator; mirrors the rule the server's
  // ``PasswordResetRequestSerializer`` enforces (``EmailField``).
  const emailError = useMemo(() => {
    const trimmed = email.trim();
    if (trimmed.length === 0) return "Please enter your institutional email.";
    if (!isValidEmail(trimmed)) return "Please enter a valid email address.";
    return null;
  }, [email]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitAttempted(true);
    setError(null);

    if (emailError) {
      return;
    }

    setIsSubmitting(true);
    try {
      // The API is intentionally idempotent: it always returns 202 whether
      // or not the email is registered, so we never reveal account existence.
      await requestPasswordReset(email.trim());
    } catch {
      // We swallow client errors for the same reason; the success state is
      // shown to every user who submits the form.
    } finally {
      setIsSubmitting(false);
      setSubmitted(true);
    }
  }

  // Only show the inline email error after the first submit attempt
  // (or when the user has typed something invalid). The pattern
  // matches the login and register pages.
  const showEmailError = submitAttempted ? emailError : null;

  return (
    <AuthShell
      title="Reset your password"
      subtitle="We'll email a one-time link to set a new password. The link is good for 30 minutes."
      altLink={{ href: "/login", label: "Back to sign in" }}
      hero={{
        eyebrow: "Step 1 of 2 — Account recovery",
        headline: "We'll send a secure reset link.",
      }}
    >
      {submitted ? (
        <div className="space-y-5">
          <StatusBanner
            tone="success"
            title="Check your inbox"
          >
            If an account exists for <span className="font-semibold">{email}</span>,
            a reset link is on its way. The link expires in 30 minutes.
          </StatusBanner>
          <Link
            href="/login"
            className="inline-flex h-12 w-full items-center justify-center rounded-full bg-ink-100 px-6 text-base font-semibold text-ink-900 transition hover:bg-ink-200"
          >
            Return to sign in
          </Link>
          <button
            type="button"
            onClick={() => {
              // Let the user re-submit with a corrected email — covers
              // the "I mistyped my address" case.
              setSubmitted(false);
              setSubmitAttempted(false);
              setError(null);
            }}
            className="block w-full text-center text-sm font-semibold text-brand-700 transition hover:text-brand-800"
          >
            Didn't get the email? Try again
          </button>
        </div>
      ) : (
        <form className="space-y-5" onSubmit={handleSubmit} noValidate>
          {error ? <StatusBanner tone="danger" title="Something went wrong" children={error} /> : null}
          <Input
            id="email"
            name="email"
            label="Institutional email"
            type="email"
            placeholder="officer@university.edu"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (error) setError(null);
            }}
            autoComplete="email"
            required
            iconLeft="mail"
            hint="Use the email you signed up with."
            error={showEmailError ?? undefined}
          />
          <Button
            type="submit"
            size="lg"
            fullWidth
            loading={isSubmitting}
            // Gate on the same validator the inline error uses, so
            // the user can't keep clicking into a broken form.
            disabled={submitAttempted && emailError !== null}
            iconRight="arrow-right"
          >
            {isSubmitting ? "Sending link…" : "Email me a reset link"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}

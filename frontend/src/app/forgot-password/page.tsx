"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBanner } from "@/components/ui/status-banner";
import { requestPasswordReset } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      // The API is intentionally idempotent: it always returns 202 whether
      // or not the email is registered, so we never reveal account existence.
      await requestPasswordReset(email);
    } catch {
      // We swallow client errors for the same reason; the success state is
      // shown to every user who submits the form.
    } finally {
      setIsSubmitting(false);
      setSubmitted(true);
    }
  }

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
        </div>
      ) : (
        <form className="space-y-5" onSubmit={handleSubmit}>
          {error ? <StatusBanner tone="danger" title="Something went wrong" children={error} /> : null}
          <Input
            id="email"
            name="email"
            label="Institutional email"
            type="email"
            placeholder="officer@university.edu"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
            iconLeft="mail"
            hint="Use the email you signed up with."
          />
          <Button
            type="submit"
            size="lg"
            fullWidth
            loading={isSubmitting}
            iconRight="arrow-right"
          >
            {isSubmitting ? "Sending link…" : "Email me a reset link"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}

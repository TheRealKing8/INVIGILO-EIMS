"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { PasswordField } from "@/components/password-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBanner } from "@/components/ui/status-banner";
import { Icon } from "@/components/ui/icon";
import { registerWithEmailPassword, saveAuthTokens } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Client-side match check — the backend still re-validates the
    // password strength on its own; this is the "you typed two
    // different passwords" guard.
    if (password !== confirmPassword) {
      setError("Passwords do not match. Please retype both fields.");
      return;
    }
    setIsSubmitting(true);
    setError(null);

    try {
      const data = await registerWithEmailPassword(fullName, email, password);
      saveAuthTokens(data.access, data.refresh, data.user);
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We couldn't create your account. Please review the details and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create your Invigilo account"
      subtitle="Exam officers, chief invigilators, and admins use Invigilo to plan sessions, allocate staff, and stay audit-ready."
      altLink={{ href: "/login", label: "Sign in instead" }}
      hero={{
        eyebrow: "Get started — Built for the exam office",
        headline: "From roster to report — in one workspace.",
      }}
    >
      <form className="space-y-5" onSubmit={handleSubmit}>
        {error ? <StatusBanner tone="danger" title="We couldn't create your account" children={error} /> : null}

        <Input
          id="fullName"
          name="fullName"
          label="Full name"
          type="text"
          placeholder="Alicia Mugo"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          autoComplete="name"
          required
          iconLeft="user"
        />

        <Input
          id="email"
          name="email"
          label="Work email"
          type="email"
          placeholder="name@university.edu"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
          iconLeft="mail"
        />

        <PasswordField
          id="password"
          label="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
          hint="12+ characters, mixing at least three of: lowercase, uppercase, digit, symbol."
        />

        <PasswordField
          id="confirmPassword"
          label="Confirm password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          autoComplete="new-password"
          // Mirror state — subtle warning when the user has typed
          // both fields and they differ.
          hint={
            confirmPassword && confirmPassword !== password
              ? "Passwords do not match yet."
              : undefined
          }
        />

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={isSubmitting}
          iconRight={isSubmitting ? undefined : "check"}
        >
          {isSubmitting ? "Creating your account…" : "Create account"}
        </Button>

        <div className="flex items-center gap-3 rounded-2xl bg-ink-100 p-3 text-xs text-ink-700 ring-1 ring-inset ring-ink-200">
          <Icon name="lock" className="h-4 w-4 text-ink-500" />
          <span>
            By creating an account you accept the institutional acceptable-use
            policy. Accounts are provisioned by your exam officer.
          </span>
        </div>
      </form>
    </AuthShell>
  );
}

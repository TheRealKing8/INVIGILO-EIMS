"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { PasswordField } from "@/components/password-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBanner } from "@/components/ui/status-banner";
import { Icon } from "@/components/ui/icon";
import { registerWithEmailPassword, saveAuthTokens } from "@/lib/api";
import { validateRegister } from "@/lib/validation";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  // Field-level client errors.
  const [fullNameError, setFullNameError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmPasswordError, setConfirmPasswordError] = useState<string | null>(null);
  // Top-of-form banner for server errors (duplicate email, network, etc).
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);

  const validation = useMemo(
    () => validateRegister(fullName, email, password, confirmPassword),
    [fullName, email, password, confirmPassword],
  );

  function clearError(field: "fullName" | "email" | "password" | "confirm") {
    if (field === "fullName" && fullNameError) setFullNameError(null);
    if (field === "email" && emailError) setEmailError(null);
    if (field === "password" && passwordError) setPasswordError(null);
    if (field === "confirm" && confirmPasswordError) setConfirmPasswordError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitAttempted(true);
    setServerError(null);

    // Run the full validator; mirror the per-field errors into state so the
    // user sees them inline.
    const v = validateRegister(fullName, email, password, confirmPassword);
    setFullNameError(v.fullName);
    setEmailError(v.email);
    setPasswordError(v.password);
    setConfirmPasswordError(v.confirmPassword);
    if (!v.isValid) {
      return;
    }

    setIsSubmitting(true);
    try {
      const data = await registerWithEmailPassword(fullName, email, password);
      // The refresh token is delivered as an httpOnly cookie by the
      // server; ``data.refresh`` is only present for non-browser
      // clients (CLI, mobile, tests). We never read or persist it on
      // the web — the cookie travels automatically on every request.
      saveAuthTokens(data.access, data.user);
      router.push("/dashboard");
    } catch (err) {
      setServerError(
        err instanceof Error
          ? err.message
          : "We couldn't create your account. Please review the details and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  // Only show inline errors after the first submit attempt.
  const showFullNameError = submitAttempted ? fullNameError : null;
  const showEmailError = submitAttempted ? emailError : null;
  const showPasswordError = submitAttempted ? passwordError : null;
  const showConfirmError = submitAttempted ? confirmPasswordError : null;

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
      <form className="space-y-5" onSubmit={handleSubmit} noValidate>
        {serverError ? (
          <StatusBanner tone="danger" title="We couldn't create your account">
            {serverError}
          </StatusBanner>
        ) : null}

        <Input
          id="fullName"
          name="fullName"
          label="Full name"
          type="text"
          placeholder="Alicia Mugo"
          value={fullName}
          onChange={(e) => {
            setFullName(e.target.value);
            clearError("fullName");
            if (serverError) setServerError(null);
          }}
          autoComplete="name"
          required
          iconLeft="user"
          error={showFullNameError ?? undefined}
        />

        <Input
          id="email"
          name="email"
          label="Work email"
          type="email"
          placeholder="name@university.edu"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            clearError("email");
            if (serverError) setServerError(null);
          }}
          autoComplete="email"
          required
          iconLeft="mail"
          error={showEmailError ?? undefined}
        />

        <PasswordField
          id="password"
          label="Password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            clearError("password");
            if (serverError) setServerError(null);
          }}
          required
          autoComplete="new-password"
          hint="12+ characters, mixing at least three of: lowercase, uppercase, digit, symbol."
          error={showPasswordError ?? undefined}
        />

        <PasswordField
          id="confirmPassword"
          label="Confirm password"
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

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { PasswordField } from "@/components/password-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBanner } from "@/components/ui/status-banner";
import { Icon } from "@/components/ui/icon";
import {
  getStoredAccessToken,
  loginWithEmailPassword,
  saveAuthTokens,
} from "@/lib/api";
import { notifyAuthChange } from "@/lib/auth";

const DEMO_CREDENTIALS = {
  email: "admininvigilo@gmail.com",
  password: "Invigilo@2026",
};

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (getStoredAccessToken()) {
      router.replace("/dashboard");
    }
  }, [router]);

  function useDemoCredentials() {
    setEmail(DEMO_CREDENTIALS.email);
    setPassword(DEMO_CREDENTIALS.password);
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const data = await loginWithEmailPassword(email, password);
      saveAuthTokens(data.access, data.refresh, data.user);
      // Fan out to any <AuthProvider> subscribers so the route guards
      // see the new user on the very next render.
      notifyAuthChange();
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We couldn't sign you in. Double-check your credentials and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Sign in to Invigilo"
      subtitle="Pick up where the operations team left off — sessions, allocations, incidents, and reports in one workspace."
      altLink={{ href: "/register", label: "Request an officer account" }}
      hero={{
        eyebrow: "Welcome back — Operations console",
        headline: "Run examinations, not spreadsheets.",
      }}
    >
      <form className="space-y-5" onSubmit={handleSubmit}>
        {error ? <StatusBanner tone="danger" title="We couldn't sign you in" children={error} /> : null}

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
        />

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="password"
              className="text-sm font-medium text-ink-700"
            >
              Password
            </label>
            <Link
              href="/forgot-password"
              className="text-xs font-semibold text-brand-700 transition hover:text-brand-800"
            >
              Forgot password?
            </Link>
          </div>
          <PasswordField
            id="password"
            label=""
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={isSubmitting}
          iconRight={isSubmitting ? undefined : "arrow-right"}
        >
          {isSubmitting ? "Signing you in…" : "Continue to dashboard"}
        </Button>

        <button
          type="button"
          onClick={useDemoCredentials}
          className="group flex w-full items-center gap-3 rounded-2xl bg-brand-50 p-3 text-left text-xs text-brand-900 ring-1 ring-inset ring-brand-100 transition hover:bg-brand-100 hover:ring-brand-200"
        >
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-brand-700 ring-1 ring-inset ring-brand-200">
            <Icon name="sparkle" className="h-3.5 w-3.5" />
          </span>
          <span className="flex-1 leading-relaxed">
            <span className="block font-semibold">Use demo credentials</span>
            <span className="mt-0.5 block text-[11px] text-brand-800/80">
              {DEMO_CREDENTIALS.email} · {DEMO_CREDENTIALS.password}
            </span>
          </span>
          <Icon
            name="arrow-right"
            className="h-3.5 w-3.5 text-brand-700 transition group-hover:translate-x-0.5"
          />
        </button>
      </form>
    </AuthShell>
  );
}

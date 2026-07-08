"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { PasswordField } from "@/components/password-field";
import { getStoredAccessToken, loginWithEmailPassword, saveAuthTokens } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (getStoredAccessToken()) {
      router.replace("/dashboard");
    }
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setStatus(null);

    try {
      const data = await loginWithEmailPassword(email, password);
      saveAuthTokens(data.access, data.refresh, data.user);
      setStatus(`Signed in as ${data.user.email}`);
      router.push("/dashboard");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to sign in right now.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Sign in to INVIGILO"
      subtitle="Access the university examination operations workspace with your secure institutional credentials."
      footerText="Need a demo account?"
      footerLink={{ href: "/register", label: "Create one here" }}
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div>
          <label htmlFor="email" className="mb-2 block text-sm font-medium text-slate-700">
            Email address
          </label>
          <input
            id="email"
            type="email"
            placeholder="officer@university.edu"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none ring-0 focus:border-emerald-600"
            required
          />
        </div>
        <PasswordField
          id="password"
          label="Password"
          placeholder="••••••••"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        <button
          type="submit"
          disabled={isSubmitting}
          className="flex w-full items-center justify-center rounded-full bg-emerald-700 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-70"
        >
          {isSubmitting ? "Signing in..." : "Continue to dashboard"}
        </button>
      </form>

      {status ? (
        <p className={`mt-4 text-sm ${status.startsWith("Signed in") ? "text-emerald-700" : "text-rose-700"}`}>
          {status}
        </p>
      ) : null}

      <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        <p>
          Not registered yet?{' '}
          <Link href="/register" className="font-semibold text-emerald-700">
            Create your account
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}

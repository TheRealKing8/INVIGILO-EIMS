"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { PasswordField } from "@/components/password-field";
import { registerWithEmailPassword, saveAuthTokens } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("Use your institutional email to create a secure account.");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setStatus("");

    try {
      const data = await registerWithEmailPassword(fullName, email, password);
      saveAuthTokens(data.access, data.refresh, data.user);
      setStatus(`Welcome aboard, ${data.user.email}`);
      router.push("/dashboard");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to create your account right now.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create your INVIGILO account"
      subtitle="Register as an examination officer, chief invigilator, or administrative user to manage exam operations."
      footerText="Already have an account?"
      footerLink={{ href: "/login", label: "Sign in" }}
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div>
          <label htmlFor="fullName" className="mb-2 block text-sm font-medium text-slate-700">
            Full name
          </label>
          <input
            id="fullName"
            type="text"
            placeholder="Alicia Mugo"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none ring-0 focus:border-emerald-600"
            required
          />
        </div>
        <div>
          <label htmlFor="email" className="mb-2 block text-sm font-medium text-slate-700">
            Work email
          </label>
          <input
            id="email"
            type="email"
            placeholder="name@university.edu"
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
          {isSubmitting ? "Creating account..." : "Create account"}
        </button>
      </form>

      {status ? (
        <p className={`mt-4 text-sm ${status.startsWith("Welcome") ? "text-emerald-700" : "text-rose-700"}`}>
          {status}
        </p>
      ) : null}

      <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        <p>
          Already using INVIGILO?{' '}
          <Link href="/login" className="font-semibold text-emerald-700">
            Sign in instead
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}

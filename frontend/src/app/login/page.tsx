"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChangeEvent,
  ClipboardEvent,
  FormEvent,
  KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AuthShell } from "@/components/auth-shell";
import { PasswordField } from "@/components/password-field";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { StatusBanner } from "@/components/ui/status-banner";
import {
  getStoredAccessToken,
  loginWithEmailPassword,
  saveAuthTokens,
  selectRoleOnLogin,
  verifyLoginOtp,
  type AuthUser,
  type AvailableRole,
} from "@/lib/api";
import { notifyAuthChange } from "@/lib/auth";
import { validateLogin } from "@/lib/validation";

const OTP_LENGTH = 6;

type Step = "credentials" | "role" | "otp";

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("credentials");
  // Step 1 — credentials
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  // Step 2a — role pick (Phase 21, only for multi-role users)
  const [availableRoles, setAvailableRoles] = useState<AvailableRole[]>([]);
  const [loginToken, setLoginToken] = useState<string | null>(null);
  // Step 2b — OTP (Phase 21 may be reached from credentials OR from role pick)
  const [otpDigits, setOtpDigits] = useState<string[]>(
    Array.from({ length: OTP_LENGTH }, () => ""),
  );
  const [otpToken, setOtpToken] = useState<string | null>(null);
  // Shared
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Track whether the user has tried to submit at least once — before that we
  // don't show inline errors so the form doesn't shout at first paint.
  const [submitAttempted, setSubmitAttempted] = useState(false);
  // Resend state
  const [resendIn, setResendIn] = useState(0);
  const otpInputRefs = useRef<Array<HTMLInputElement | null>>([]);

  const validation = useMemo(
    () => validateLogin(email, password),
    [email, password],
  );

  // Bounce already-authenticated users to the dashboard. We only check on
  // first mount; the post-OTP redirect handles the rest.
  useEffect(() => {
    if (getStoredAccessToken()) {
      router.replace("/dashboard");
    }
  }, [router]);

  // Resend cooldown timer.
  useEffect(() => {
    if (resendIn <= 0) return;
    const t = window.setTimeout(() => setResendIn(resendIn - 1), 1000);
    return () => window.clearTimeout(t);
  }, [resendIn]);

  // Auto-advance the OTP input focus as the user types.
  useEffect(() => {
    if (step !== "otp") return;
    const filled = otpDigits.findIndex((d) => d === "");
    const target = filled === -1 ? OTP_LENGTH - 1 : filled;
    otpInputRefs.current[target]?.focus();
  }, [otpDigits, step]);

  async function handleCredentialsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitAttempted(true);
    setServerError(null);

    const v = validateLogin(email, password);
    setEmailError(v.email);
    setPasswordError(v.password);
    if (!v.isValid) {
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await loginWithEmailPassword(email, password);
      // The server returns one of three shapes (Phase 21, see
      // ``LoginResult`` in api.ts):
      //   1. { requires_role_pick, available_roles, login_token }
      //      — multi-role user, show the picker
      //   2. { requires_otp, otp_token }
      //      — single-role staff user, second step required
      //   3. AuthTokens
      //      — proceed as before
      if ("requires_role_pick" in result) {
        setAvailableRoles(result.available_roles);
        setLoginToken(result.login_token);
        // Phase 21 — the server may also pre-issue an otp_token so
        // the staff-pick hand-off doesn't have to round-trip again.
        // We stash it for the OTP step; if the user picks a
        // non-staff role, it's simply unused.
        if (result.requires_otp && result.otp_token) {
          setOtpToken(result.otp_token);
        }
        setStep("role");
        return;
      }
      if ("requires_otp" in result && result.otp_token) {
        setOtpToken(result.otp_token);
        setOtpDigits(Array.from({ length: OTP_LENGTH }, () => ""));
        setStep("otp");
        setResendIn(60);
        return;
      }
      // Normal login: persist tokens and route to dashboard. The
      // refresh token arrives as an httpOnly cookie, so we never
      // see or store it on the client. By this point both the
      // role-pick and OTP branches have returned, so ``result`` is
      // the ``AuthTokens`` variant.
      const tokens = result as Extract<typeof result, { access: string; user: AuthUser }>;
      saveAuthTokens(tokens.access, tokens.user);
      notifyAuthChange();
      router.push("/dashboard");
    } catch (err) {
      setServerError(
        err instanceof Error
          ? err.message
          : "We couldn't sign you in. Double-check your credentials and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRoleSelect(role: AvailableRole) {
    if (!loginToken) return;
    setIsSubmitting(true);
    setServerError(null);
    try {
      const result = await selectRoleOnLogin(loginToken, role.code);
      if ("requires_otp" in result) {
        // The chosen role is staff — hand off to the OTP step.
        // We carry the ``login_token`` through to the verify step
        // so the server can re-issue the JWT against the chosen
        // role, not the user's primary role.
        setOtpToken(result.otp_token);
        setOtpDigits(Array.from({ length: OTP_LENGTH }, () => ""));
        setStep("otp");
        setResendIn(60);
        return;
      }
      // Non-staff pick: tokens in hand, route to dashboard.
      saveAuthTokens(result.access, result.user);
      notifyAuthChange();
      router.push("/dashboard");
    } catch (err) {
      setServerError(
        err instanceof Error
          ? err.message
          : "We couldn't complete the role pick. Please try again.",
      );
      // The role-pick session might be expired (5-min TTL). Drop
      // back to credentials so the user can re-authenticate.
      setStep("credentials");
      setLoginToken(null);
      setAvailableRoles([]);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOtpSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!otpToken) return;
    const code = otpDigits.join("");
    if (code.length !== OTP_LENGTH) {
      setServerError("Enter the 6-digit code from your email.");
      return;
    }
    setSubmitAttempted(true);
    setServerError(null);
    setIsSubmitting(true);
    try {
      // Phase 21 — if we came through the role-pick step, we have a
      // ``login_token`` to carry through so the verify step can
      // re-issue the JWT against the chosen role.
      const tokens = await verifyLoginOtp(otpToken, code, loginToken ?? undefined);
      saveAuthTokens(tokens.access, tokens.user);
      notifyAuthChange();
      router.push("/dashboard");
    } catch (err) {
      // The server collapses every failure into a single opaque
      // "Invalid or expired code" message, so we surface the same
      // generic copy the API returns.
      setServerError(
        err instanceof Error
          ? err.message
          : "Invalid or expired code.",
      );
      // Clear the digits so the user can re-type without manually
      // backspacing through the boxes.
      setOtpDigits(Array.from({ length: OTP_LENGTH }, () => ""));
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleOtpDigitChange(
    index: number,
    e: ChangeEvent<HTMLInputElement>,
  ) {
    const raw = e.target.value;
    // Strip non-digits and clamp to one character. Paste events
    // arrive as the full string in ``change``; we let the paste
    // handler own that flow.
    const digit = raw.replace(/\D/g, "").slice(-1);
    setOtpDigits((prev) => {
      const next = [...prev];
      next[index] = digit;
      return next;
    });
    if (serverError) setServerError(null);
  }

  function handleOtpDigitKeyDown(
    index: number,
    e: KeyboardEvent<HTMLInputElement>,
  ) {
    if (e.key === "Backspace" && !otpDigits[index] && index > 0) {
      // Backspace in an empty box jumps to the previous box.
      e.preventDefault();
      otpInputRefs.current[index - 1]?.focus();
    } else if (e.key === "ArrowLeft" && index > 0) {
      e.preventDefault();
      otpInputRefs.current[index - 1]?.focus();
    } else if (e.key === "ArrowRight" && index < OTP_LENGTH - 1) {
      e.preventDefault();
      otpInputRefs.current[index + 1]?.focus();
    }
  }

  function handleOtpPaste(e: ClipboardEvent<HTMLInputElement>) {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "");
    if (pasted.length === 0) return;
    e.preventDefault();
    const next = Array.from({ length: OTP_LENGTH }, (_, i) => pasted[i] ?? "");
    setOtpDigits(next);
    if (serverError) setServerError(null);
    // Focus the last filled box (or the last box if all are filled).
    const lastFilled = Math.min(pasted.length, OTP_LENGTH) - 1;
    otpInputRefs.current[Math.max(0, lastFilled)]?.focus();
  }

  async function handleResend() {
    if (resendIn > 0 || isSubmitting) return;
    setIsSubmitting(true);
    setServerError(null);
    try {
      const result = await loginWithEmailPassword(email, password);
      if ("requires_otp" in result && result.otp_token) {
        setOtpToken(result.otp_token);
        setOtpDigits(Array.from({ length: OTP_LENGTH }, () => ""));
        setResendIn(60);
      }
    } catch (err) {
      setServerError(
        err instanceof Error
          ? err.message
          : "We couldn't resend the code. Try again in a moment.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleUseDifferentAccount() {
    setStep("credentials");
    setOtpToken(null);
    setOtpDigits(Array.from({ length: OTP_LENGTH }, () => ""));
    setLoginToken(null);
    setAvailableRoles([]);
    setServerError(null);
    setSubmitAttempted(false);
    setResendIn(0);
  }

  // Only render inline errors after the first submit attempt.
  const showEmailError = submitAttempted ? emailError : null;
  const showPasswordError = submitAttempted ? passwordError : null;

  if (step === "role") {
    return (
      <AuthShell
        title="Pick a role for this session"
        subtitle={`${email} holds more than one role — choose the one you want to sign in as. You can switch later by signing out.`}
        hero={{
          eyebrow: "Almost there — Operations console",
          headline: "Different hats, same operator.",
        }}
      >
        <div className="space-y-5">
          {serverError ? (
            <StatusBanner tone="danger" title="We couldn't complete the role pick">
              {serverError}
            </StatusBanner>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2">
            {availableRoles.map((role) => (
              <button
                key={role.code}
                type="button"
                onClick={() => handleRoleSelect(role)}
                disabled={isSubmitting}
                className="group flex flex-col items-start gap-1.5 rounded-2xl border border-ink-200 bg-surface p-4 text-left shadow-[var(--shadow-card)] transition hover:border-brand-400 hover:shadow-[var(--shadow-card-hover)] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <div className="flex w-full items-center justify-between">
                  <span className="text-sm font-semibold text-ink-900">
                    {role.name}
                  </span>
                  <Icon
                    name="arrow-right"
                    className="h-4 w-4 text-ink-400 transition group-hover:text-brand-600"
                  />
                </div>
                <span className="text-xs font-mono uppercase tracking-wide text-brand-700">
                  {role.code}
                </span>
                {role.description ? (
                  <span className="text-xs text-ink-600">
                    {role.description}
                  </span>
                ) : null}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs">
            <button
              type="button"
              onClick={handleUseDifferentAccount}
              className="font-medium text-ink-600 transition hover:text-ink-900"
            >
              Use a different account
            </button>
            <span className="text-ink-500">
              This choice lasts until you sign out.
            </span>
          </div>
        </div>
      </AuthShell>
    );
  }

  if (step === "otp") {
    return (
      <AuthShell
        title="Enter your one-time code"
        subtitle={`We sent a 6-digit code to ${email}. It expires in 10 minutes.`}
        hero={{
          eyebrow: "Almost there — Operations console",
          headline: "Two-step verification keeps admin access locked down.",
        }}
      >
        <form className="space-y-5" onSubmit={handleOtpSubmit} noValidate>
          {serverError ? (
            <StatusBanner tone="danger" title="That code didn't work">
              {serverError}
            </StatusBanner>
          ) : null}

          <div>
            <label
              htmlFor="otp-0"
              className="text-sm font-medium text-ink-700"
            >
              One-time code
            </label>
            <div
              className="mt-2 flex justify-between gap-2"
              role="group"
              aria-label="One-time code, 6 digits"
            >
              {otpDigits.map((digit, i) => (
                <input
                  key={i}
                  ref={(el) => {
                    otpInputRefs.current[i] = el;
                  }}
                  id={`otp-${i}`}
                  type="text"
                  inputMode="numeric"
                  autoComplete={i === 0 ? "one-time-code" : "off"}
                  pattern="[0-9]*"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleOtpDigitChange(i, e)}
                  onKeyDown={(e) => handleOtpDigitKeyDown(i, e)}
                  onPaste={handleOtpPaste}
                  aria-label={`Digit ${i + 1} of ${OTP_LENGTH}`}
                  className="h-14 w-12 rounded-2xl border border-ink-200 bg-surface text-center text-2xl font-semibold tnum text-ink-900 shadow-[var(--shadow-card)] outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
                />
              ))}
            </div>
            <p className="mt-2 text-xs text-ink-500">
              Paste a 6-digit code from your email and the boxes will fill in automatically.
            </p>
          </div>

          <Button
            type="submit"
            size="lg"
            fullWidth
            loading={isSubmitting}
            disabled={otpDigits.join("").length !== OTP_LENGTH}
            iconRight={isSubmitting ? undefined : "arrow-right"}
          >
            {isSubmitting ? "Verifying…" : "Verify and continue"}
          </Button>

          <div className="flex items-center justify-between text-xs">
            <button
              type="button"
              onClick={handleResend}
              disabled={resendIn > 0 || isSubmitting}
              className="font-semibold text-brand-700 transition hover:text-brand-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {resendIn > 0 ? `Resend code in ${resendIn}s` : "Resend code"}
            </button>
            <button
              type="button"
              onClick={handleUseDifferentAccount}
              className="font-medium text-ink-600 transition hover:text-ink-900"
            >
              Use a different account
            </button>
          </div>
        </form>
      </AuthShell>
    );
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
      <form className="space-y-5" onSubmit={handleCredentialsSubmit} noValidate>
        {serverError ? (
          <StatusBanner tone="danger" title="We couldn't sign you in">
            {serverError}
          </StatusBanner>
        ) : null}

        <Input
          id="email"
          name="email"
          label="Institutional email"
          type="email"
          placeholder="officer@university.edu"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (emailError) setEmailError(null);
            if (serverError) setServerError(null);
          }}
          autoComplete="email"
          required
          iconLeft="mail"
          error={showEmailError ?? undefined}
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
            onChange={(e) => {
              setPassword(e.target.value);
              if (passwordError) setPasswordError(null);
              if (serverError) setServerError(null);
            }}
            required
            autoComplete="current-password"
            error={showPasswordError ?? undefined}
          />
        </div>

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={isSubmitting}
          // Keep the button enabled at first so the user can click and see
          // the inline errors appear; once a submit has been attempted the
          // gate tightens so the user can't keep clicking into a broken form.
          disabled={submitAttempted && !validation.isValid}
          iconRight={isSubmitting ? undefined : "arrow-right"}
        >
          {isSubmitting ? "Signing you in…" : "Continue to dashboard"}
        </Button>
      </form>
    </AuthShell>
  );
}

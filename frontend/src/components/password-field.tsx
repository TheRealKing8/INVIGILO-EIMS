"use client";

import { useState, type ChangeEvent } from "react";
import { Icon } from "@/components/ui/icon";

type PasswordFieldProps = {
  id: string;
  label: string;
  placeholder?: string;
  value: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  required?: boolean;
  hint?: string;
  autoComplete?: string;
  error?: string;
};

export function PasswordField({
  id,
  label,
  placeholder = "••••••••••••",
  value,
  onChange,
  required = false,
  hint,
  autoComplete = "current-password",
  error,
}: PasswordFieldProps) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-sm font-medium text-ink-700"
      >
        {label}
      </label>
      <div className="relative">
        <Icon
          name="lock"
          className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
        />
        <input
          id={id}
          type={isVisible ? "text" : "password"}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          required={required}
          autoComplete={autoComplete}
          className={[
            "block w-full rounded-2xl border-0 bg-ink-100/60 px-4 py-3 pl-10 pr-12 text-sm text-ink-900",
            "placeholder:text-ink-400 ring-1 ring-inset transition",
            error
              ? "ring-rose-300 focus:ring-rose-500"
              : "ring-ink-200 focus:bg-surface focus:ring-2 focus:ring-brand-500",
          ].join(" ")}
        />
        <button
          type="button"
          onClick={() => setIsVisible((current) => !current)}
          className="absolute inset-y-0 right-3 flex items-center text-ink-400 transition hover:text-ink-700"
          aria-label={isVisible ? "Hide password" : "Show password"}
        >
          <Icon name={isVisible ? "eye-off" : "eye"} className="h-4 w-4" />
        </button>
      </div>
      {error ? (
        <p className="mt-1.5 text-xs font-medium text-rose-600">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-xs text-ink-500">{hint}</p>
      ) : null}
    </div>
  );
}

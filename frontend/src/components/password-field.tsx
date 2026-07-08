"use client";

import { useState, type ChangeEvent } from "react";

type PasswordFieldProps = {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  required?: boolean;
};

export function PasswordField({
  id,
  label,
  placeholder,
  value,
  onChange,
  required = false,
}: PasswordFieldProps) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div>
      <label htmlFor={id} className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={isVisible ? "text" : "password"}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 pr-12 text-sm outline-none ring-0 focus:border-emerald-600"
          required={required}
        />
        <button
          type="button"
          onClick={() => setIsVisible((current) => !current)}
          className="absolute inset-y-0 right-3 flex items-center text-slate-500 transition hover:text-slate-700"
          aria-label={isVisible ? "Hide password" : "Show password"}
        >
          {isVisible ? (
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M3 12s3-6 9-6 9 6 9 6-3 6-9 6-9-6-9-6Z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M3 3l18 18" />
              <path d="M10.6 10.6A3 3 0 0 0 13.4 13.4" />
              <path d="M9 5.2A10.9 10.9 0 0 1 12 5c6 0 9 7 9 7a17.7 17.7 0 0 1-2.3 3.2" />
              <path d="M6.5 6.5A16.7 16.7 0 0 0 3 12s3 7 9 7a10.5 10.5 0 0 0 3.1-.5" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}

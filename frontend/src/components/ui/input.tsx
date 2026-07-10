/**
 * Input — a single styled text field that the rest of the app composes.
 *
 * The `Input` is intentionally a controlled component that does not own
 * state — the parent (a form) holds the value so it can run validation.
 */
import { type InputHTMLAttributes, forwardRef } from "react";
import { Icon, type IconName } from "@/components/ui/icon";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
  iconLeft?: IconName;
  iconRight?: IconName;
  inputClassName?: string;
};

const fieldClass =
  "block w-full rounded-2xl border-0 bg-ink-100/60 px-4 py-3 text-sm text-ink-900 " +
  "placeholder:text-ink-400 ring-1 ring-inset ring-ink-200 transition " +
  "focus:bg-surface focus:ring-2 focus:ring-brand-500";

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, iconLeft, iconRight, id, inputClassName = "", ...rest },
  ref,
) {
  const inputId = id ?? rest.name;
  return (
    <div>
      <label
        htmlFor={inputId}
        className="mb-1.5 block text-sm font-medium text-ink-700"
      >
        {label}
      </label>
      <div className="relative">
        {iconLeft ? (
          <Icon
            name={iconLeft}
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
          />
        ) : null}
        <input
          ref={ref}
          id={inputId}
          {...rest}
          className={[
            fieldClass,
            iconLeft ? "pl-10" : "",
            iconRight ? "pr-10" : "",
            error
              ? "ring-rose-300 focus:ring-rose-500"
              : "focus:ring-brand-500",
            inputClassName,
          ].join(" ")}
        />
        {iconRight ? (
          <Icon
            name={iconRight}
            className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
          />
        ) : null}
      </div>
      {error ? (
        <p className="mt-1.5 text-xs font-medium text-rose-600">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-xs text-ink-500">{hint}</p>
      ) : null}
    </div>
  );
});

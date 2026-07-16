/**
 * PasswordStrengthMeter — visual feedback for the register form.
 *
 * Renders a 4-segment stacked bar that lights up as the typed
 * password grows stronger, plus a label (Weak / OK / Good / Strong /
 * Very strong) and a 3-bullet checklist of the complexity rules
 * the user is being asked to hit.
 *
 *   <PasswordStrengthMeter value={password} />
 *
 * The score function is shared with the validator in ``lib/validation``
 * so the meter cannot disagree with the form-level "is this acceptable?"
 * check. The thresholds are intentionally generous — the meter is
 * feedback, not a gate. The validator is the real gate.
 */
"use client";

import {
  passwordChecklist,
  passwordStrengthScore,
  type PasswordStrength,
} from "@/lib/validation";
import { Icon } from "@/components/ui/icon";

const SCORE_LABEL: Record<PasswordStrength, string> = {
  0: "Too short",
  1: "Weak",
  2: "OK",
  3: "Strong",
  4: "Very strong",
};

// The bar is 4 segments; the active color is the "on" tone for the
// current score. Inactive segments share one muted ink tone so the
// bar reads as a single unit until the user starts typing.
const TONE_BAR: Record<PasswordStrength, string> = {
  0: "bg-rose-500",
  1: "bg-rose-500",
  2: "bg-amber-500",
  3: "bg-emerald-500",
  4: "bg-emerald-600",
};

const TONE_LABEL: Record<PasswordStrength, string> = {
  0: "text-rose-700",
  1: "text-rose-700",
  2: "text-amber-700",
  3: "text-emerald-700",
  4: "text-emerald-700",
};

const INACTIVE = "bg-ink-200";

export function PasswordStrengthMeter({ value }: { value: string }) {
  const score = passwordStrengthScore(value);
  const checklist = passwordChecklist(value);

  return (
    <div className="mt-2 space-y-2" aria-live="polite">
      {/* Bar: 4 segments. The first N segments are tinted by the current
          tone; the rest stay muted. */}
      <div className="flex items-center gap-1.5" role="presentation">
        {[0, 1, 2, 3].map((segment) => {
          const isActive = segment < score;
          return (
            <div
              key={segment}
              className={[
                "h-1.5 flex-1 rounded-full transition-colors",
                isActive ? TONE_BAR[score] : INACTIVE,
              ].join(" ")}
              aria-hidden
            />
          );
        })}
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className={`font-semibold ${TONE_LABEL[score]}`}>
          {SCORE_LABEL[score]}
        </span>
        <span className="text-ink-500">
          {value.length === 0
            ? "Start typing to see strength"
            : `${value.length} character${value.length === 1 ? "" : "s"}`}
        </span>
      </div>

      {/* Checklist: 3 bullets tracking the rules. Always rendered so the
          layout doesn't jump as the user types. */}
      <ul className="space-y-1 text-xs text-ink-600">
        <ChecklistRow passed={checklist.hasMinLength}>
          At least 6 characters
        </ChecklistRow>
        <ChecklistRow passed={checklist.hasThreeClasses}>
          Mix at least 3 of: lowercase, uppercase, digit, symbol
        </ChecklistRow>
        <ChecklistRow passed={checklist.hasFourClasses}>
          Bonus: all 4 character classes (very strong)
        </ChecklistRow>
      </ul>
    </div>
  );
}

function ChecklistRow({
  passed,
  children,
}: {
  passed: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-center gap-2">
      <Icon
        name={passed ? "check" : "x"}
        className={[
          "h-3.5 w-3.5",
          passed ? "text-emerald-600" : "text-ink-400",
        ].join(" ")}
      />
      <span className={passed ? "text-ink-700" : "text-ink-500"}>
        {children}
      </span>
    </li>
  );
}

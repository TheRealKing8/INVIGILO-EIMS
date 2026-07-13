/**
 * Client-side validation for the auth pages.
 *
 * These rules mirror the backend in ``backend/apps/accounts/validators.py``
 * and ``backend/apps/accounts/serializers.py`` so the user gets fast, friendly
 * feedback for the common mistakes without round-tripping to the API. The
 * server is still the source of truth — if the client somehow lets bad data
 * through (e.g. an old tab with stale JS), the API will still reject it.
 *
 * The complexity regex set is intentionally identical to
 * ``validators.py:38-42`` so the client and the server agree on what
 * "three of four character classes" means.
 */

const PATTERNS = {
  lowercase: /[a-z]/,
  uppercase: /[A-Z]/,
  digit: /\d/,
  symbol: /[^A-Za-z0-9]/,
} as const;

const REQUIRED_CLASSES = 3;

const MIN_LENGTH = 12;

/** Common passwords blocked on the server. Mirrors ``validators.py:65-78``. */
export const COMMON_PASSWORDS: ReadonlySet<string> = new Set([
  "password",
  "12345678",
  "123456789",
  "1234567890",
  "qwerty123",
  "letmein123",
  "welcome1!",
  "admin1234",
  "iloveyou!",
  "p@ssw0rd",
]);

/** A simple RFC-5322-ish email regex matching DRF's ``EmailField``. */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export type ValidationResult = { ok: true } | { ok: false; message: string };

export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim());
}

export function isValidFullName(value: string): ValidationResult {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return { ok: false, message: "Please enter your full name." };
  }
  if (trimmed.length < 2) {
    return { ok: false, message: "Please enter your full name (at least 2 characters)." };
  }
  return { ok: true };
}

export function isValidPassword(value: string): ValidationResult {
  if (!value) {
    return { ok: false, message: "Please choose a password." };
  }
  if (value.length < MIN_LENGTH) {
    return {
      ok: false,
      message: `Password must be at least ${MIN_LENGTH} characters.`,
    };
  }
  const present = Object.values(PATTERNS).filter((re) => re.test(value)).length;
  if (present < REQUIRED_CLASSES) {
    return {
      ok: false,
      message: `Password must contain at least ${REQUIRED_CLASSES} of: lowercase, uppercase, digit, symbol.`,
    };
  }
  if (COMMON_PASSWORDS.has(value.toLowerCase())) {
    return { ok: false, message: "That password is too common — please choose another." };
  }
  return { ok: true };
}

export function passwordMatches(password: string, confirm: string): boolean {
  return password.length > 0 && password === confirm;
}

/**
 * Aggregate validity for the login form. Returns the first error per field
 * (or null if valid). The pages render these as inline messages and use the
 * overall `isValid` flag to gate the submit button.
 */
export type LoginValidation = {
  email: string | null;
  password: string | null;
  isValid: boolean;
};

export function validateLogin(email: string, password: string): LoginValidation {
  const emailError = email.trim().length === 0
    ? "Please enter your institutional email."
    : !isValidEmail(email)
    ? "Please enter a valid email address."
    : null;
  const passwordError = password.length === 0 ? "Please enter your password." : null;
  return {
    email: emailError,
    password: passwordError,
    isValid: emailError === null && passwordError === null,
  };
}

export type RegisterValidation = {
  fullName: string | null;
  email: string | null;
  password: string | null;
  confirmPassword: string | null;
  isValid: boolean;
};

export function validateRegister(
  fullName: string,
  email: string,
  password: string,
  confirmPassword: string,
): RegisterValidation {
  const fullNameResult = isValidFullName(fullName);
  const fullNameError = fullNameResult.ok ? null : fullNameResult.message;

  const emailError = email.trim().length === 0
    ? "Please enter your work email."
    : !isValidEmail(email)
    ? "Please enter a valid email address."
    : null;

  const passwordResult = isValidPassword(password);
  const passwordError = passwordResult.ok ? null : passwordResult.message;

  // Only show the "do not match" error once the user has typed something in
  // both fields — otherwise the message would be premature on first render.
  const confirmError =
    confirmPassword.length > 0 && !passwordMatches(password, confirmPassword)
      ? "Passwords do not match."
      : null;

  return {
    fullName: fullNameError,
    email: emailError,
    password: passwordError,
    confirmPassword: confirmError,
    isValid:
      fullNameError === null &&
      emailError === null &&
      passwordError === null &&
      confirmError === null,
  };
}

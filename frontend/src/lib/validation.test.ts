/**
 * Unit tests for ``src/lib/validation.ts``.
 *
 * These mirror the backend's ``apps/accounts/validators.py`` 1:1 so
 * that any drift between client and server rules surfaces here
 * first. The pattern is: a ``describe`` per export, then
 * table-driven ``it`` cases covering the happy path, the obvious
 * failures, and the edge cases (empty, whitespace, common-password).
 */
import { describe, expect, it } from "vitest";

import {
  COMMON_PASSWORDS,
  isValidEmail,
  isValidFullName,
  isValidPassword,
  passwordChecklist,
  passwordMatches,
  passwordStrengthScore,
  validateLogin,
  validateRegister,
} from "./validation";

describe("isValidEmail", () => {
  it.each([
    "name@university.edu",
    "a@b.co",
    "first.last+tag@sub.domain.io",
    "x@y.z",
  ])("accepts %s", (value) => {
    expect(isValidEmail(value)).toBe(true);
  });

  it.each([
    "",
    "no-at-symbol",
    "@no-local-part.com",
    "no-domain@",
    "spaces in@email.com",
    "trailing@",
    "@leading.com",
  ])("rejects %s", (value) => {
    expect(isValidEmail(value)).toBe(false);
  });

  it("trims surrounding whitespace before validating", () => {
    expect(isValidEmail("  name@university.edu  ")).toBe(true);
  });
});

describe("isValidFullName", () => {
  it("accepts a single non-empty name of 2+ characters", () => {
    expect(isValidFullName("Alicia Mugo")).toEqual({ ok: true });
    expect(isValidFullName("Bo")).toEqual({ ok: true });
  });

  it("rejects empty / whitespace-only input", () => {
    expect(isValidFullName("")).not.toEqual({ ok: true });
    expect(isValidFullName("   ")).not.toEqual({ ok: true });
  });

  it("rejects single-character input", () => {
    expect(isValidFullName("A")).toEqual({
      ok: false,
      message: "Please enter your full name (at least 2 characters).",
    });
  });

  it("trims before checking length", () => {
    expect(isValidFullName("  Bo  ")).toEqual({ ok: true });
  });
});

describe("isValidPassword", () => {
  describe("length (MinimumLengthValidator)", () => {
    it("rejects empty", () => {
      const r = isValidPassword("");
      expect(r.ok).toBe(false);
    });

    it("rejects 5 characters even with 3-of-4 complexity", () => {
      // 5 chars, lower + upper + digit. Just under the bar (Phase 21
      // lowered the floor from 12 to 6).
      const r = isValidPassword("Abcd1");
      expect(r).toEqual({
        ok: false,
        message: "Password must be at least 6 characters.",
      });
    });

    it("accepts 6 characters with 3-of-4 complexity", () => {
      // 6 chars, lower + upper + digit. The new minimum.
      const r = isValidPassword("Abcde1");
      expect(r.ok).toBe(true);
    });
  });

  describe("complexity (ComplexityValidator — 3 of 4 classes)", () => {
    it("rejects 8 chars of a single class (lowercase only)", () => {
      const r = isValidPassword("abcdefgh");
      expect(r.ok).toBe(false);
      expect((r as { ok: false; message: string }).message).toMatch(/at least 3 of/i);
    });

    it("rejects 6 chars with only 2 classes (lower + upper)", () => {
      const r = isValidPassword("AbcdeF");
      expect(r.ok).toBe(false);
    });

    it("rejects 6 chars with only 2 classes (lower + digit)", () => {
      const r = isValidPassword("abcde1");
      expect(r.ok).toBe(false);
    });

    it("accepts 6 chars with 3 classes (lower + upper + digit)", () => {
      expect(isValidPassword("Abcde1").ok).toBe(true);
    });

    it("accepts 6 chars with 4 classes (all four)", () => {
      expect(isValidPassword("Abcde!").ok).toBe(true);
    });
  });

  describe("common-password block (CommonPasswordValidator)", () => {
    // The function runs checks in order: length → complexity → common.
    // Since the canonical common passwords are all 8-10 chars and the
    // minimum is 6, the common-password branch is reachable for any
    // common password that's also 6+ chars (e.g. "password" is 8
    // chars and would normally pass the length check — but the
    // common-password list catches it first when complexity allows).

    it("rejects 6-10 char common passwords", () => {
      // We don't pin which validator catches each — the canonical
      // common-password set is full of low-complexity, low-entropy
      // strings (single class, two classes, all-digits, etc.) so the
      // length, complexity, and common-password checks all fire
      // depending on the input. What we care about is the union:
      // every one of these is rejected.
      const shouldReject = [
        "123456",
        "1234567",
        "password",
        "12345678",
        "admin1234",
        "qwerty123",
        "p@ssw0rd",
        "letmein123",
        "welcome1!",
        "iloveyou!",
      ];
      for (const pw of shouldReject) {
        const r = isValidPassword(pw);
        expect(r.ok, `expected "${pw}" to be rejected`).toBe(false);
      }
    });

    it("the COMMON_PASSWORDS set is keyed on lower-cased full strings", () => {
      // Direct assertions on the helper. The validator consults
      // COMMON_PASSWORDS via ``value.toLowerCase()`` — so the
      // validator's behaviour is case-insensitive even though the
      // set itself contains only lower-cased entries.
      expect(COMMON_PASSWORDS.has("p@ssw0rd")).toBe(true);
      expect(COMMON_PASSWORDS.has("P@SSW0RD")).toBe(false); // set stores lower-case
      expect(COMMON_PASSWORDS.has("Tr0ub4dor&3xyz")).toBe(false);
    });
  });

  describe("happy path", () => {
    it.each([
      "Abcde1",
      "Strong-Pass-2026",
      "Tr0ub4dor&3xyz", // xkcd-correct-horse staple
      "CorrectHorseBattery!",
    ])("accepts %s", (pw) => {
      expect(isValidPassword(pw).ok).toBe(true);
    });
  });
});

describe("passwordStrengthScore (Phase 21 strength meter)", () => {
  it("returns 0 for empty input", () => {
    expect(passwordStrengthScore("")).toBe(0);
  });

  it("returns 0 for inputs below the 6-char minimum", () => {
    expect(passwordStrengthScore("Ab1")).toBe(0);
    expect(passwordStrengthScore("Abcde")).toBe(0);
  });

  it("returns 1 for length-met but no class variety", () => {
    // 6 chars, single class. The meter rates this as "Weak" (1) —
    // it's past the length floor but the complexity rule is the real
    // gate.
    expect(passwordStrengthScore("abcdef")).toBe(1);
  });

  it("returns 2 for length-met + 3-of-4 complexity", () => {
    expect(passwordStrengthScore("Abcde1")).toBe(2);
  });

  it("returns 2 for length-met + 3-of-4 complexity (no digit)", () => {
    // Lower + upper + symbol, no digit.
    expect(passwordStrengthScore("Abcde!")).toBe(2);
  });

  it("returns 3 for length-met + all 4 classes", () => {
    expect(passwordStrengthScore("Abcde1!")).toBe(3);
  });

  it("returns 4 for length-met + all 4 classes + 16+ chars", () => {
    // 16 chars, 4 classes.
    expect(passwordStrengthScore("Abcdefgh1!@#$%^&")).toBe(4);
  });
});

describe("passwordChecklist (Phase 21 strength meter)", () => {
  it("reports all three rules unmet for empty input", () => {
    expect(passwordChecklist("")).toEqual({
      hasMinLength: false,
      hasThreeClasses: false,
      hasFourClasses: false,
    });
  });

  it("reports hasMinLength true at exactly 6 chars", () => {
    expect(passwordChecklist("Abcde1").hasMinLength).toBe(true);
  });

  it("reports hasThreeClasses true when 3 of 4 classes are present", () => {
    expect(passwordChecklist("Abcde1").hasThreeClasses).toBe(true);
    expect(passwordChecklist("Abcde1").hasFourClasses).toBe(false);
  });

  it("reports hasFourClasses true when all 4 classes are present", () => {
    expect(passwordChecklist("Abcde1!").hasFourClasses).toBe(true);
  });
});

describe("passwordMatches", () => {
  it("returns true when both are non-empty and equal", () => {
    expect(passwordMatches("hunter2hunter2", "hunter2hunter2")).toBe(true);
  });

  it("returns false when they differ", () => {
    expect(passwordMatches("hunter2hunter2", "hunter3hunter3")).toBe(false);
  });

  it("returns false when either side is empty", () => {
    expect(passwordMatches("", "anything")).toBe(false);
    expect(passwordMatches("anything", "")).toBe(false);
    expect(passwordMatches("", "")).toBe(false);
  });
});

describe("COMMON_PASSWORDS", () => {
  it("contains the canonical top offenders", () => {
    for (const pw of ["password", "qwerty123", "admin1234", "p@ssw0rd"]) {
      expect(COMMON_PASSWORDS.has(pw)).toBe(true);
    }
  });

  it("does not flag a strong, uncommon password", () => {
    expect(COMMON_PASSWORDS.has("Tr0ub4dor&3xyz")).toBe(false);
    expect(COMMON_PASSWORDS.has("Strong-Pass-2026")).toBe(false);
    expect(COMMON_PASSWORDS.has("P@ssw0rd!Strong")).toBe(false);
  });
});

describe("validateLogin", () => {
  it("is valid with a real email and non-empty password", () => {
    const v = validateLogin("officer@x.edu", "hunter2hunter2");
    expect(v).toEqual({ email: null, password: null, isValid: true });
  });

  it("rejects empty email", () => {
    const v = validateLogin("", "hunter2hunter2");
    expect(v.email).toMatch(/please enter/i);
    expect(v.isValid).toBe(false);
  });

  it("rejects malformed email", () => {
    const v = validateLogin("not-an-email", "hunter2hunter2");
    expect(v.email).toMatch(/valid email/i);
    expect(v.isValid).toBe(false);
  });

  it("rejects empty password", () => {
    const v = validateLogin("officer@x.edu", "");
    expect(v.password).toMatch(/please enter your password/i);
    expect(v.isValid).toBe(false);
  });

  it("is invalid when both fields are empty", () => {
    const v = validateLogin("", "");
    expect(v.isValid).toBe(false);
    expect(v.email).not.toBeNull();
    expect(v.password).not.toBeNull();
  });
});

describe("validateRegister", () => {
  const OK_NAME = "Alicia Mugo";
  const OK_EMAIL = "officer@x.edu";
  const OK_PW = "Strong-Pass-2026";

  it("is valid with all four fields filled correctly", () => {
    const v = validateRegister(OK_NAME, OK_EMAIL, OK_PW, OK_PW);
    expect(v.isValid).toBe(true);
    expect(v.fullName).toBeNull();
    expect(v.email).toBeNull();
    expect(v.password).toBeNull();
    expect(v.confirmPassword).toBeNull();
  });

  it("reports a fullName error for 1-character input", () => {
    const v = validateRegister("A", OK_EMAIL, OK_PW, OK_PW);
    expect(v.fullName).toMatch(/at least 2 characters/i);
    expect(v.isValid).toBe(false);
  });

  it("reports an email error for an empty email", () => {
    const v = validateRegister(OK_NAME, "", OK_PW, OK_PW);
    expect(v.email).toMatch(/please enter your work email/i);
    expect(v.isValid).toBe(false);
  });

  it("reports a password error for a short password", () => {
    const v = validateRegister(OK_NAME, OK_EMAIL, "short", "short");
    expect(v.password).toMatch(/at least 6 characters/i);
    expect(v.isValid).toBe(false);
  });

  it("reports a password error for missing complexity", () => {
    const v = validateRegister(OK_NAME, OK_EMAIL, "abcdef", "abcdef");
    expect(v.password).toMatch(/at least 3 of/i);
    expect(v.isValid).toBe(false);
  });

  it("does not surface a confirmPassword error when the confirm field is empty", () => {
    // The UX rule from the implementation: we don't shout at the user
    // for an empty confirm field — they haven't typed yet.
    const v = validateRegister(OK_NAME, OK_EMAIL, OK_PW, "");
    expect(v.confirmPassword).toBeNull();
    expect(v.isValid).toBe(true);
  });

  it("reports a confirmPassword error when both fields are typed and differ", () => {
    const v = validateRegister(OK_NAME, OK_EMAIL, OK_PW, "Different-2026");
    expect(v.confirmPassword).toMatch(/do not match/i);
    expect(v.isValid).toBe(false);
  });

  it("aggregates multiple errors at once", () => {
    const v = validateRegister("A", "not-an-email", "short", "different");
    expect(v.fullName).not.toBeNull();
    expect(v.email).not.toBeNull();
    expect(v.password).not.toBeNull();
    expect(v.confirmPassword).not.toBeNull();
    expect(v.isValid).toBe(false);
  });
});

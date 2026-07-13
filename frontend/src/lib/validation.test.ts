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
  passwordMatches,
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

    it("rejects 11 characters even with 3-of-4 complexity", () => {
      // 11 chars, lower + upper + digit. Just under the bar.
      const r = isValidPassword("Abcdefgh1jk");
      expect(r).toEqual({
        ok: false,
        message: "Password must be at least 12 characters.",
      });
    });
  });

  describe("complexity (ComplexityValidator — 3 of 4 classes)", () => {
    it("rejects 12 chars of a single class (lowercase only)", () => {
      const r = isValidPassword("abcdefghijkl");
      expect(r.ok).toBe(false);
      expect((r as { ok: false; message: string }).message).toMatch(/at least 3 of/i);
    });

    it("rejects 12 chars with only 2 classes (lower + upper)", () => {
      const r = isValidPassword("Abcdefghijkl");
      expect(r.ok).toBe(false);
    });

    it("rejects 12 chars with only 2 classes (lower + digit)", () => {
      const r = isValidPassword("abcdefgh1234");
      expect(r.ok).toBe(false);
    });

    it("accepts 12 chars with 3 classes (lower + upper + digit)", () => {
      expect(isValidPassword("Abcdefgh1234").ok).toBe(true);
    });

    it("accepts 12 chars with 4 classes (all four)", () => {
      expect(isValidPassword("Abcdefgh1!@#").ok).toBe(true);
    });
  });

  describe("common-password block (CommonPasswordValidator)", () => {
    // The function runs checks in order: length → complexity → common.
    // Since the canonical common passwords are all 8-10 chars and the
    // minimum is 12, the common-password branch is only reachable for
    // exactly-the-set entries. We document that behavior here.

    it("rejects 8-10 char common passwords on the length check first", () => {
      for (const pw of ["password", "12345678", "admin1234", "qwerty123", "p@ssw0rd"]) {
        const r = isValidPassword(pw);
        expect(r.ok).toBe(false);
        expect((r as { ok: false; message: string }).message).toMatch(
          /at least 12 characters/i,
        );
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
      "Strong-Pass-2026",
      "Tr0ub4dor&3xyz", // xkcd-correct-horse staple
      "CorrectHorseBattery!",
    ])("accepts %s", (pw) => {
      expect(isValidPassword(pw).ok).toBe(true);
    });
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
    expect(v.password).toMatch(/at least 12 characters/i);
    expect(v.isValid).toBe(false);
  });

  it("reports a password error for missing complexity", () => {
    const v = validateRegister(OK_NAME, OK_EMAIL, "abcdefghijkl", "abcdefghijkl");
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

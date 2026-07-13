/**
 * Auth public smoke — exercises the unauthenticated user flows
 * (login form, register form, forgot-password form) which don't
 * require a backend. The dashboard flow (login → dashboard → logout)
 * lives in a separate spec gated on a known seeded user.
 *
 * These always run in CI.
 */
import { expect, test } from "@playwright/test";

test.describe("Auth (public surface)", () => {
  test("login page renders email + password + submit", async ({ page }) => {
    await page.goto("/login");
    // Use accessible names so we don't collide with any other email
    // inputs the layout might mount (e.g. the AI assistant panel).
    await expect(page.getByLabel(/^institutional email$/i)).toBeVisible();
    await expect(page.getByLabel(/^password$/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /continue to dashboard|sign in|log in/i })).toBeVisible();
  });

  test("register page renders full name + email + password + submit", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByLabel(/^full name$/i)).toBeVisible();
    await expect(page.getByLabel(/^work email$/i)).toBeVisible();
    await expect(page.getByLabel(/^password$/i)).toBeVisible();
    await expect(page.getByLabel(/^confirm password$/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /create account/i })).toBeVisible();
  });

  test("forgot password page renders email + submit", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(page.getByLabel(/^institutional email$/i)).toBeVisible();
  });

  test("unauthenticated visit to /dashboard redirects to /login", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL(/\/login/, { timeout: 5_000 });
    await expect(page.getByLabel(/^institutional email$/i)).toBeVisible();
  });

  test("reset-password page renders when token is present in URL", async ({ page }) => {
    // The link from the email is /reset-password?token=… — even a
    // bogus token should still render the form. The server's 400 only
    // surfaces after submit.
    await page.goto("/reset-password?token=fake");
    await expect(page.getByLabel(/^new password$/i)).toBeVisible();
    await expect(page.getByLabel(/^confirm new password$/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /reset password/i })).toBeVisible();
  });

  test("forgot password rejects invalid email inline", async ({ page }) => {
    await page.goto("/forgot-password");
    const emailField = page.getByLabel(/^institutional email$/i);
    await emailField.fill("not-an-email");
    // Submit is disabled while invalid, so just verify the button is
    // disabled and the inline error hasn't appeared yet (we haven't
    // tried to submit). Then submit and watch the error appear.
    const submit = page.getByRole("button", { name: /email me a reset link/i });
    // After typing invalid, with submitAttempted still false, the
    // button is enabled (the form is permissive on first paint to
    // match the login/register pattern). Clicking it triggers the
    // inline error.
    await submit.click();
    await expect(page.getByText(/please enter a valid email address/i)).toBeVisible();
  });
});

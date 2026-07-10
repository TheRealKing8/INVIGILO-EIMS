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
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByRole("button", { name: /continue to dashboard|sign in|log in/i })).toBeVisible();
  });

  test("register page renders full name + email + password + submit", async ({ page }) => {
    await page.goto("/register");
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test("forgot password page renders email + submit", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });

  test("unauthenticated visit to /dashboard redirects to /login", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL(/\/login/, { timeout: 5_000 });
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });
});

/**
 * 404 + global error smoke — exercises the route-level boundaries
 * added in Phase 4. These work without a backend.
 */
import { expect, test } from "@playwright/test";

test.describe("Route boundaries", () => {
  test("404 page renders for unknown routes", async ({ page }) => {
    const response = await page.goto("/this-route-does-not-exist");
    expect(response?.status()).toBe(404);
    await expect(page.getByText(/couldn't find/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /dashboard/i })).toBeVisible();
  });

  test("not-found page has a working link back to /dashboard", async ({ page }) => {
    await page.goto("/totally-unknown");
    await page.getByRole("link", { name: /dashboard/i }).click();
    await page.waitForURL(/\/dashboard|\/login/, { timeout: 5_000 });
  });
});

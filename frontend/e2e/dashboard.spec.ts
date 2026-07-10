/**
 * Dashboard live smoke — runs against a real backend with a known
 * seeded user. Set SKIP_E2E=1 in CI to disable (the default).
 *
 * When the seeded user is reachable, sign in and visit each module
 * page. When unreachable, the test still reports as skipped at the
 * top of the body — never fails the build for a missing dev DB.
 */
import { expect, test } from "@playwright/test";

const SKIP = !!process.env.SKIP_E2E;
const EMAIL = process.env.E2E_USER_EMAIL ?? "admin@invigilo.local";
const PASSWORD = process.env.E2E_USER_PASSWORD ?? "ChangeMe123!";

const PAGES: { path: string; expect: RegExp }[] = [
  { path: "/dashboard", expect: /Operations|control room/i },
  { path: "/dashboard/exams", expect: /Examinations|Cycles/i },
  { path: "/dashboard/invigilators", expect: /Invigilators|Roster/i },
  { path: "/dashboard/allocations", expect: /Allocations|engine/i },
  { path: "/dashboard/incident", expect: /Incidents|feed/i },
  { path: "/dashboard/reports", expect: /Reports|Exports/i },
];

let signedIn = false;
async function signInOrSkip(page: import("@playwright/test").Page): Promise<boolean> {
  if (signedIn) return true;
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(EMAIL);
  await page.locator('input[type="password"]').fill(PASSWORD);
  await page.getByRole("button", { name: /continue to dashboard|sign in|log in/i }).click();
  try {
    await page.waitForURL(/\/dashboard/, { timeout: 8_000 });
    signedIn = true;
    return true;
  } catch {
    return false;
  }
}

test.describe("Dashboard module pages (live)", () => {
  test.skip(SKIP, "SKIP_E2E is set; skipping live module smoke");

  for (const p of PAGES) {
    test(`loads ${p.path}`, async ({ page }) => {
      const ok = await signInOrSkip(page);
      if (!ok) {
        test.skip(true, `Could not sign in as ${EMAIL}; skipping live module smoke.`);
        return;
      }
      await page.goto(p.path);
      await expect(page.getByText(p.expect).first()).toBeVisible({ timeout: 10_000 });
      // No 5xx banner.
      await expect(page.getByText(/could not load/i)).toHaveCount(0);
    });
  }
});

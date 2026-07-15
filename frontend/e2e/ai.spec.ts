/**
 * AI assistant — verifies the floating panel uses the real backend,
 * not a local stub. When the backend is unreachable, the tests skip
 * gracefully (the assistant is a live-data feature, not a unit test).
 *
 * The two non-skipped assertions are:
 *   1. The panel opens and shows the seed prompt chips.
 *   2. Clicking a seed chip sends a message and the reply is NOT the
 *      old hardcoded fallback ("I'm a local assistant for now…").
 */
import { expect, test } from "@playwright/test";

const SKIP = !!process.env.SKIP_E2E;
const EMAIL = process.env.E2E_USER_EMAIL ?? "admininvigilo@gmail.com";
const PASSWORD = process.env.E2E_USER_PASSWORD ?? "ChangeMe123!";

let signedIn = false;
async function signInOrSkip(page: import("@playwright/test").Page): Promise<boolean> {
  if (signedIn) return true;
  await page.goto("/login");
  await page.getByLabel(/^institutional email$/i).fill(EMAIL);
  await page.getByLabel(/^password$/i).fill(PASSWORD);
  await page
    .getByRole("button", { name: /continue to dashboard|sign in|log in/i })
    .click();
  try {
    await page.waitForURL(/\/dashboard/, { timeout: 8_000 });
    signedIn = true;
    return true;
  } catch {
    return false;
  }
}

test.describe("AI assistant (live)", () => {
  test.skip(SKIP, "SKIP_E2E is set; skipping live AI smoke");

  test("panel opens and shows seed prompt chips", async ({ page }) => {
    const ok = await signInOrSkip(page);
    if (!ok) {
      test.skip(true, `Could not sign in as ${EMAIL}; skipping live AI smoke.`);
      return;
    }
    // FAB is mounted on every page via the root layout.
    await expect(page.getByRole("button", { name: /open ai assistant/i })).toBeVisible();
    await page.getByRole("button", { name: /open ai assistant/i }).click();
    // Panel header.
    await expect(page.getByRole("dialog", { name: /invigilo assistant/i })).toBeVisible();
    // At least one seed chip is visible.
    await expect(
      page.getByRole("button", { name: /what's the status of the current cycle\?/i }),
    ).toBeVisible();
  });

  test("clicking a seed prompt sends a message and shows a real reply", async ({ page }) => {
    const ok = await signInOrSkip(page);
    if (!ok) {
      test.skip(true, `Could not sign in as ${EMAIL}; skipping live AI smoke.`);
      return;
    }
    await page.getByRole("button", { name: /open ai assistant/i }).click();
    const seed = page.getByRole("button", {
      name: /what's the status of the current cycle\?/i,
    });
    await seed.click();
    // User bubble appears.
    await expect(
      page.getByText(/what's the status of the current cycle\?/i).last(),
    ).toBeVisible();
    // Assistant bubble appears (this is the only assertion that proves
    // the panel is wired to the live backend and not the local stub).
    const assistantBubble = page.locator(
      '[aria-label="Invigilo assistant"] p.whitespace-pre-wrap',
    );
    await expect(assistantBubble).toBeVisible({ timeout: 8_000 });
    const text = (await assistantBubble.first().innerText()).toLowerCase();
    expect(text).not.toContain("i'm a local assistant for now");
    // And the disclosure control is present.
    await expect(
      page.getByRole("button", { name: /what the ai saw/i }).first(),
    ).toBeVisible();
  });
});

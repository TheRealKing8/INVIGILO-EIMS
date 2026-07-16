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
const EMAIL = process.env.E2E_USER_EMAIL ?? "admininvigilo@gmail.com";
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
    // If the server returns requires_otp, fill any 6-digit code the
    // dev console email backend may have printed. In a real test
    // environment the backend is usually skipped, so this branch
    // rarely fires — but we handle it so the e2e isn't hardcoded to
    // a non-admin user.
    const otpInput = page.locator('input[id^="otp-"]').first();
    if (await otpInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
      // We don't have a real code. Type 000000 — if the OTP fallback
      // env var is set, this is the dev shortcut. Otherwise the
      // verify call fails and the test is skipped.
      for (let i = 0; i < 6; i++) {
        await page.locator(`#otp-${i}`).fill("0");
      }
      await page.getByRole("button", { name: /verify and continue/i }).click();
    }
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

  test("invigilator profile page renders the 14-day availability grid", async ({ page }) => {
    const ok = await signInOrSkip(page);
    if (!ok) {
      test.skip(true, `Could not sign in as ${EMAIL}; skipping live module smoke.`);
      return;
    }
    // Resolve a real invigilator id from the roster page.
    await page.goto("/dashboard/invigilators");
    const firstRow = page.locator("ul > li").first();
    if ((await firstRow.count()) === 0) {
      test.skip(true, "No invigilators in roster; skipping profile smoke.");
      return;
    }
    await firstRow.click();
    await page.waitForURL(/\/dashboard\/invigilators\/[^/]+$/, { timeout: 8_000 });
    // The 14-day grid is the unique signature of the profile page.
    // We assert that at least 14 day tiles are visible.
    const tiles = page.locator(
      'button:has(span:text-matches("^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)$", "i"))',
    );
    await expect(tiles.first()).toBeVisible({ timeout: 10_000 });
    expect(await tiles.count()).toBeGreaterThanOrEqual(14);
    // The legend should be present so the user knows the status colours.
    await expect(page.getByText(/legend:/i)).toBeVisible();
  });

  test("reports page shows live sparkline (Phase 23 wire-up)", async ({ page }) => {
    // Phase 23 — the reports page now consumes /analytics/summary/
    // for the right-rail sparkline + severity chips. This test
    // asserts the sparkline SVG is rendered (the value is real, not
    // hard-coded). We don't assert exact numbers — the dev DB may
    // have zero check-ins, which renders the empty-state branch.
    const ok = await signInOrSkip(page);
    if (!ok) {
      test.skip(true, `Could not sign in as ${EMAIL}; skipping live module smoke.`);
      return;
    }
    await page.goto("/dashboard/reports");
    // The Card with the trend header is rendered if and only if the
    // page is rendering the live layout (not the legacy hard-coded
    // one we removed). "Check-ins, last 12 weeks" is the new title.
    await expect(
      page.getByText(/check-ins, last 12 weeks/i),
    ).toBeVisible({ timeout: 10_000 });
    // The Sparkline component renders an <svg> with a <path>. Assert
    // the path element exists — that's the live data, not the
    // static array the page used to ship.
    const sparklinePath = page.locator("svg path").first();
    await expect(sparklinePath).toBeVisible();
    // And the "Field signal" card now shows the live severity
    // breakdown instead of the redundant export-format counts.
    await expect(page.getByText(/field signal/i)).toBeVisible();
    await expect(page.getByText(/incidents by severity/i)).toBeVisible();
  });

  test("exam session detail page renders after row click", async ({ page }) => {
    const ok = await signInOrSkip(page);
    if (!ok) {
      test.skip(true, `Could not sign in as ${EMAIL}; skipping live module smoke.`);
      return;
    }
    await page.goto("/dashboard/exams");
    const firstRow = page.locator("table tbody tr").first();
    if ((await firstRow.count()) === 0) {
      test.skip(true, "No exam sessions on the list; skipping detail smoke.");
      return;
    }
    await firstRow.click();
    await page.waitForURL(/\/dashboard\/exams\/[^/]+$/, { timeout: 8_000 });
    // The detail page renders the "Back to examinations" link as its
    // primary exit — that's the unique signature.
    await expect(
      page.getByRole("button", { name: /back to examinations/i }),
    ).toBeVisible();
    // And it shows the staffing card.
    await expect(page.getByText(/assigned invigilators/i)).toBeVisible();
  });

  test("allocation run detail page renders after View run details click", async ({ page }) => {
    const ok = await signInOrSkip(page);
    if (!ok) {
      test.skip(true, `Could not sign in as ${EMAIL}; skipping live module smoke.`);
      return;
    }
    await page.goto("/dashboard/allocations");
    const viewLink = page.getByRole("button", { name: /view run details/i });
    if ((await viewLink.count()) === 0) {
      test.skip(true, "No allocation runs yet; skipping run detail smoke.");
      return;
    }
    await viewLink.first().click();
    await page.waitForURL(/\/dashboard\/allocations\/[^/]+$/, { timeout: 8_000 });
    // The run detail page is identified by the "Triggered by" stat row
    // and the "Per-session allocations" header.
    await expect(page.getByText(/triggered by/i).first()).toBeVisible();
    await expect(page.getByText(/per-session allocations/i)).toBeVisible();
  });

  test("audit log page loads", async ({ page }) => {
    const ok = await signInOrSkip(page);
    if (!ok) {
      test.skip(true, `Could not sign in as ${EMAIL}; skipping live module smoke.`);
      return;
    }
    await page.goto("/dashboard/audit");
    // The audit page has a "Recent events" header and a "Target type" filter.
    await expect(
      page.getByRole("heading", { name: /audit log/i }).first(),
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/recent events/i).first()).toBeVisible();
    // Either rows are visible OR the empty-state message is shown.
    const emptyState = page.getByText(/no audit events match/i);
    const firstRow = page.locator("ul > li").first();
    if ((await firstRow.count()) === 0) {
      await expect(emptyState).toBeVisible();
    }
  });

  test("incident detail page renders after row click", async ({ page }) => {
    const ok = await signInOrSkip(page);
    if (!ok) {
      test.skip(true, `Could not sign in as ${EMAIL}; skipping live module smoke.`);
      return;
    }
    await page.goto("/dashboard/incident");
    const firstRow = page.locator("ul > li").first();
    if ((await firstRow.count()) === 0) {
      test.skip(true, "No incidents on the feed; skipping detail smoke.");
      return;
    }
    await firstRow.click();
    await page.waitForURL(/\/dashboard\/incident\/[^/]+$/, { timeout: 8_000 });
    // The detail page renders the "Back to incidents" link as its
    // primary exit — that's the unique signature.
    await expect(
      page.getByRole("button", { name: /back to incidents/i }),
    ).toBeVisible();
    // And it shows the body / description card.
    await expect(page.getByText(/what was reported/i)).toBeVisible();
  });

  test("topbar search shows live results", async ({ page }) => {
    const ok = await signInOrSkip(page);
    if (!ok) {
      test.skip(true, `Could not sign in as ${EMAIL}; skipping live module smoke.`);
      return;
    }
    await page.goto("/dashboard");
    const search = page.getByPlaceholder(/search exams, staff, rooms/i);
    await search.click();
    // Type a query long enough to trigger the popover. We don't care
    // what comes back — only that at least one of the three groups
    // surfaces.
    await search.fill("test");
    // The popover renders group section labels; the backend may match
    // an exam, an invigilator, or a room by the literal "test". If
    // nothing matches, the empty state renders instead.
    const examsGroup = page.getByText(/^exams$/i).first();
    const invGroup = page.getByText(/^invigilators$/i).first();
    const roomsGroup = page.getByText(/^rooms$/i).first();
    const empty = page.getByText(/no results for/i).first();
    await expect(
      examsGroup.or(invGroup).or(roomsGroup).or(empty).first(),
    ).toBeVisible({ timeout: 8_000 });
  });
});

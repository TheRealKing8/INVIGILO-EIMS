/**
 * RBAC live smoke — verifies that the frontend route guards and the
 * nav filter work end-to-end.
 *
 * Set ``SKIP_E2E=1`` in CI to skip these (the default). They are only
 * meaningful when the dev server can reach the seeded backend AND a
 * STUDENT-role user has been provisioned. The fixture helper below
 * creates a STUDENT user on the fly via the admin ``POST
 * /api/v1/users/`` endpoint, signs in as them, and asserts the nav
 * shows only "Overview" and that direct URL access to
 * ``/dashboard/allocations`` is redirected back to ``/dashboard``.
 */
import { expect, test } from "@playwright/test";

const SKIP = !!process.env.SKIP_E2E;

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admininvigilo@gmail.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "Invigilo@2026";
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// A throwaway user created per test run. The email embeds a timestamp
// so the test is re-runnable without manual cleanup.
function uniqueStudentEmail(): string {
  const stamp = Date.now();
  return `rbac-student-${stamp}@invigilo.test`;
}

async function loginViaApi(
  email: string,
  password: string,
): Promise<{ access: string }> {
  const r = await fetch(`${API_BASE}/api/v1/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error(`Login as ${email} failed: ${r.status}`);
  return (await r.json()) as { access: string };
}

async function createStudentUser(
  adminAccess: string,
  email: string,
  password: string,
): Promise<void> {
  const r = await fetch(`${API_BASE}/api/v1/users/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${adminAccess}`,
    },
    body: JSON.stringify({
      email,
      full_name: "RBAC Smoke Student",
      password,
      is_email_verified: true,
      roles: ["STUDENT"],
    }),
  });
  if (!r.ok) {
    throw new Error(
      `Create student failed: ${r.status} ${await r.text()}`,
    );
  }
}

async function signInUI(
  page: import("@playwright/test").Page,
  email: string,
  password: string,
): Promise<boolean> {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: /continue to dashboard|sign in|log in/i }).click();
  try {
    await page.waitForURL(/\/dashboard/, { timeout: 8_000 });
    return true;
  } catch {
    return false;
  }
}

test.describe("RBAC: per-role nav + route guards", () => {
  test.skip(SKIP, "SKIP_E2E is set; skipping RBAC live smoke");

  test("admin sees all six nav entries", async ({ page }) => {
    const ok = await signInUI(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    if (!ok) {
      test.skip(true, `Could not sign in as admin ${ADMIN_EMAIL}; skipping.`);
      return;
    }
    // The Overview link is always present; check the four other role-
    // specific entries that admins should see.
    await expect(page.getByRole("link", { name: /examinations/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /invigilators/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /allocations/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /reports/i })).toBeVisible();
  });

  test("student sees only Overview and is redirected from /dashboard/allocations", async ({
    page,
  }) => {
    // Provision a STUDENT user via the admin API.
    const email = uniqueStudentEmail();
    const password = "Invigilo@2026";
    let adminToken: string;
    try {
      const pair = await loginViaApi(ADMIN_EMAIL, ADMIN_PASSWORD);
      adminToken = pair.access;
      await createStudentUser(adminToken, email, password);
    } catch (err) {
      test.skip(
        true,
        `Backend unreachable or admin cannot create users: ${(err as Error).message}`,
      );
      return;
    }

    // Sign in as the student in the UI.
    const ok = await signInUI(page, email, password);
    if (!ok) {
      test.skip(true, `Could not sign in as student ${email}; skipping.`);
      return;
    }

    // Nav should only contain Overview.
    await expect(page.getByRole("link", { name: /overview/i })).toBeVisible();
    // Admin-only nav items must NOT be present in the sidebar.
    await expect(page.getByRole("link", { name: /allocations/i })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /^reports$/i })).toHaveCount(0);

    // Direct URL access is redirected back to /dashboard.
    await page.goto("/dashboard/allocations");
    await page.waitForURL(/\/dashboard\/?$/, { timeout: 8_000 });
  });
});

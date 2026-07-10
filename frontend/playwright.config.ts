/**
 * Playwright config — end-to-end smoke tests.
 *
 * Targets Chromium only (cheaper CI, no real cross-browser matrix for
 * a smoke suite). The webServer block boots `next start` against the
 * production build so the test mirrors what production looks like;
 * in dev mode, point PW at `npm run dev` if you want hot reload.
 *
 * Tests live in `frontend/e2e/*.spec.ts`.
 */
import { defineConfig, devices } from "@playwright/test";

const PORT = process.env.PW_PORT ?? "3100";
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `next start -p ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});

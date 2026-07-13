/**
 * Vitest configuration.
 *
 * Mirrors the path alias in ``tsconfig.json`` (``@/* -> ./src/*``) so
 * tests can import modules the same way the app does. The default
 * Node environment is fine for ``lib/validation.ts`` (pure functions)
 * and any future service-layer tests. Component tests can opt in to
 * the ``jsdom`` env per-file with ``// @vitest-environment jsdom``.
 */
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
  },
});

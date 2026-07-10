/**
 * Theme — light / dark / system, persisted to localStorage.
 *
 * Architecture
 * ------------
 * 1. <ThemeScript /> is a server-rendered <script> injected as the first
 *    child of <body> in app/layout.tsx. It reads the user's stored
 *    preference and the OS media query, then sets
 *    `document.documentElement.dataset.theme` *before* React hydrates so
 *    the first frame is already in the right colors (no FOUC).
 *
 * 2. <ThemeProvider /> wraps the app on the client. It owns the
 *    `theme` state ("light" | "dark" | "system"), keeps it in sync with
 *    localStorage, and listens to `matchMedia` so "system" follows the
 *    OS theme live.
 *
 * 3. useTheme() exposes { theme, resolvedTheme, setTheme } to any
 *    client component. The components that need to know the active
 *    theme are: <ThemeToggle /> (icon + dropdown highlight) and
 *    <BrandMark /> in dark-mode-aware contexts (none today, but the
 *    API is here for when we add it).
 *
 * Components themselves never need to read the theme — the design
 * tokens in globals.css flip automatically off [data-theme="dark"].
 */

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ThemeChoice = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

type ThemeContextValue = {
  theme: ThemeChoice;
  resolvedTheme: ResolvedTheme;
  setTheme: (next: ThemeChoice) => void;
};

const STORAGE_KEY = "invigilo-theme";

const ThemeContext = createContext<ThemeContextValue | null>(null);

function isThemeChoice(value: string | null): value is ThemeChoice {
  return value === "light" || value === "dark" || value === "system";
}

function readStoredTheme(): ThemeChoice {
  if (typeof window === "undefined") return "system";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isThemeChoice(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

function resolveTheme(theme: ThemeChoice): ResolvedTheme {
  if (theme === "light" || theme === "dark") return theme;
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyResolvedTheme(resolved: ResolvedTheme) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
}

/**
 * ThemeScript — runs once, synchronously, before paint.
 *
 * Renders an inline <script> that reads localStorage + the OS media
 * query and sets `data-theme` on <html>. The React tree hydrates over
 * a correctly-colored page.
 */
export function ThemeScript() {
  // The function body is intentionally a string literal so it ships
  // verbatim, with no closure over module state, and is safe to render
  // in a server component.
  const code = `
(function() {
  try {
    var stored = localStorage.getItem("${STORAGE_KEY}");
    var theme = (stored === "light" || stored === "dark" || stored === "system") ? stored : "system";
    var resolved = theme === "system"
      ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      : theme;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.style.colorScheme = resolved;
  } catch (e) {
    document.documentElement.dataset.theme = "light";
  }
})();
`.trim();
  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Initial state is read from storage on the client. On the server,
  // the lazy initializer runs against `undefined` window and returns
  // the safe "system" / "light" defaults — the inline <ThemeScript />
  // then upgrades <html> before the first paint. This keeps SSR and
  // the first client render in agreement and avoids setState-in-effect.
  const [theme, setThemeState] = useState<ThemeChoice>(() => {
    if (typeof window === "undefined") return "system";
    return readStoredTheme();
  });
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => {
    if (typeof window === "undefined") return "light";
    const initial = readStoredTheme();
    const resolved = resolveTheme(initial);
    applyResolvedTheme(resolved);
    return resolved;
  });

  // Subscribe to OS theme changes; only react when the user is on
  // "system". The effect body never calls setState synchronously
  // (it only sets state in the matchMedia change callback).
  useEffect(() => {
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const onSystemChange = () => {
      // Re-read storage in case the user changed the choice while we
      // weren't looking (e.g. another tab).
      const current = readStoredTheme();
      if (current === "system") {
        const next = resolveTheme("system");
        setResolvedTheme(next);
        applyResolvedTheme(next);
      }
    };
    mql.addEventListener("change", onSystemChange);
    return () => mql.removeEventListener("change", onSystemChange);
  }, []);

  const setTheme = useCallback((next: ThemeChoice) => {
    setThemeState(next);
    const resolved = resolveTheme(next);
    setResolvedTheme(resolved);
    applyResolvedTheme(resolved);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage may be unavailable (private mode); the theme still
      // applies for the current session, it just won't persist.
    }
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme, setTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used inside <ThemeProvider>");
  }
  return ctx;
}

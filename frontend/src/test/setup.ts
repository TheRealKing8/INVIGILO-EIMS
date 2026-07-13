/**
 * Vitest setup — runs once per test file before any specs.
 *
 * Pulls in ``@testing-library/jest-dom`` so DOM-aware tests can use
 * matchers like ``toBeInTheDocument``. The validation tests are
 * pure-function and don't need it, but we import the matcher here
 * so future component tests get it for free.
 */
import "@testing-library/jest-dom/vitest";

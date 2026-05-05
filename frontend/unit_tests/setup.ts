/**
 * setup.ts — Vitest global setup file.
 *
 * This file runs once before every frontend test file. It:
 *   1. Imports @testing-library/jest-dom which adds extra matchers like
 *      toBeInTheDocument(), toHaveValue(), toBeDisabled(), etc.
 *   2. Cleans up the DOM after each test so components don't bleed state.
 *   3. Provides a working in-memory localStorage mock (jsdom doesn't have one).
 *
 * Vitest is told to load this file via the `setupFiles` option in vite.config.ts.
 */

import '@testing-library/jest-dom';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// ---------------------------------------------------------------------------
// localStorage mock
// jsdom's localStorage is not available in all environments. We provide an
// in-memory implementation so components that call localStorage.getItem/setItem
// (e.g. AuthContext which stores JWT tokens) work without errors in tests.
// ---------------------------------------------------------------------------
const localStorageStore: Record<string, string> = {};
const localStorageMock = {
  getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { localStorageStore[key] = value; }),
  removeItem: vi.fn((key: string) => { delete localStorageStore[key]; }),
  clear: vi.fn(() => { Object.keys(localStorageStore).forEach(k => delete localStorageStore[k]); }),
};

Object.defineProperty(globalThis, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

// ---------------------------------------------------------------------------
// Per-test cleanup
// ---------------------------------------------------------------------------
afterEach(() => {
  // Unmount all React trees so components don't bleed into the next test
  cleanup();
  // Clear localStorage so a token stored in test A doesn't trigger
  // AuthContext.fetchProfile side effects in test B
  Object.keys(localStorageStore).forEach(k => delete localStorageStore[k]);
});

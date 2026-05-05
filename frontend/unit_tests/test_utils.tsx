/**
 * test_utils.tsx — Custom render helper for frontend tests.
 *
 * Many components (like Login) call `useAuth()` which requires being wrapped
 * in an <AuthProvider>. If we just call render(<Login />) directly, we'd get
 * "useAuth must be used within an AuthProvider".
 *
 * This file exports a `renderWithAuth` function that automatically wraps any
 * component in the real AuthProvider, plus a `createMockAuthContext` helper
 * that creates a fake auth context value for tests that need specific auth state.
 */

import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { AuthProvider } from '../src/context/AuthContext';

/**
 * Wraps a component with AuthProvider before rendering.
 * Use this for any component that calls useAuth() internally.
 */
export function renderWithAuth(ui: ReactElement, options?: RenderOptions) {
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );
  return render(ui, { wrapper: Wrapper, ...options });
}

/**
 * A no-op handler that can be used as a placeholder for callback props.
 * Example: onBack={noop} onSuccess={noop}
 */
export const noop = () => {};

/**
 * Register.test.tsx — Unit tests for the Register component.
 *
 * The Register component POSTs to /api/accounts/register/ with username,
 * email, and password. We mock fetch to control what the API returns.
 *
 * Tests:
 *   ✓ Renders username, email, and password fields
 *   ✓ Renders "Create Account" submit button
 *   ✓ Calls onSuccess when registration succeeds
 *   ✓ Shows server error when registration fails (e.g., duplicate username)
 *   ✓ Calls onBack when "Back" button is clicked
 *   ✓ Calls onNavigateLogin when "Sign In" link is clicked
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Register from '../src/components/Register';
import { noop } from './test_utils';


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockRegisterSuccess() {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ username: 'newuser', email: 'new@example.com' }),
  } as any));
}

function mockRegisterFailure(errorData: Record<string, string[]>) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false,
    json: async () => errorData,
  } as any));
}

beforeEach(() => {
  vi.restoreAllMocks();
});


// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Register component', () => {
  // Register does NOT use useAuth(), so we can use plain render()
  const renderRegister = (overrides = {}) =>
    render(
      <Register
        onBack={noop}
        onSuccess={noop}
        onNavigateLogin={noop}
        {...overrides}
      />
    );

  it('renders username, email, and password inputs', () => {
    renderRegister();
    expect(screen.getByPlaceholderText('Choose a username')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('you@example.com')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument();
  });

  it('renders a Create Account submit button', () => {
    renderRegister();
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
  });

  it('calls onSuccess when registration succeeds', async () => {
    mockRegisterSuccess();
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    renderRegister({ onSuccess });

    await user.type(screen.getByPlaceholderText('Choose a username'), 'newuser');
    await user.type(screen.getByPlaceholderText('you@example.com'), 'new@example.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'password123');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it('shows error when server returns a 400 (e.g., duplicate username)', async () => {
    mockRegisterFailure({ username: ['A user with that username already exists.'] });
    const user = userEvent.setup();

    renderRegister();

    await user.type(screen.getByPlaceholderText('Choose a username'), 'existing');
    await user.type(screen.getByPlaceholderText('you@example.com'), 'x@x.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'password123');
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() =>
      expect(screen.getByText(/a user with that username already exists/i)).toBeInTheDocument()
    );
  });

  it('calls onBack when Back button is clicked', async () => {
    const onBack = vi.fn();
    const user = userEvent.setup();

    renderRegister({ onBack });
    await user.click(screen.getByRole('button', { name: /back/i }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('calls onNavigateLogin when "Sign In" link is clicked', async () => {
    const onNavigateLogin = vi.fn();
    const user = userEvent.setup();

    renderRegister({ onNavigateLogin });
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    expect(onNavigateLogin).toHaveBeenCalledTimes(1);
  });

  it('disables submit button while loading', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));  // never resolves
    const user = userEvent.setup();

    renderRegister();

    await user.type(screen.getByPlaceholderText('Choose a username'), 'someone');
    await user.type(screen.getByPlaceholderText('you@example.com'), 's@s.com');
    await user.type(screen.getByPlaceholderText('••••••••'), 'pass1234');

    // Click the submit button (it shows "Create Account" before loading starts)
    const submitBtn = document.querySelector('button[type="submit"]') as HTMLButtonElement;
    await user.click(submitBtn);

    // Once loading, the button should be disabled (it shows a spinner instead of text)
    await waitFor(() =>
      expect(document.querySelector('button[type="submit"]')).toBeDisabled()
    );
  });
});

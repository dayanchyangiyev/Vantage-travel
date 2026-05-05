/**
 * Login.test.tsx — Unit tests for the Login component.
 *
 * The Login component makes two fetch() calls:
 *   1. POST /api/accounts/login/  → get access token
 *   2. GET  /api/accounts/profile/ → get user data
 *
 * We use vi.stubGlobal('fetch', ...) to replace the browser's fetch with
 * a mock function. This way the component code does NOT need to change —
 * we intercept the network call before it ever leaves the browser.
 *
 * Tests:
 *   ✓ Renders username and password fields
 *   ✓ Renders "Sign In" submit button
 *   ✓ Calls onSuccess when login succeeds
 *   ✓ Shows error message when credentials are invalid
 *   ✓ Shows loading spinner while request is in flight
 *   ✓ Calls onBack when "Back" button is clicked
 *   ✓ Calls onNavigateRegister when "Create one" is clicked
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Login from '../src/components/Login';
import { renderWithAuth, noop } from './test_utils';


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetchSuccess() {
  const mockFetch = vi.fn()
    // First call: POST /login/ → return access token
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ access: 'fake-access-token', refresh: 'fake-refresh' }),
    } as any)
    // Second call: GET /profile/ → return user data
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1, username: 'traveler', email: 'traveler@example.com' }),
    } as any);
  vi.stubGlobal('fetch', mockFetch);
  return mockFetch;
}

function mockFetchFailure() {
  const mockFetch = vi.fn().mockResolvedValueOnce({
    ok: false,
    json: async () => ({ detail: 'No active account found with the given credentials' }),
  } as any);
  vi.stubGlobal('fetch', mockFetch);
  return mockFetch;
}

beforeEach(() => {
  vi.restoreAllMocks();
});


// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Login component', () => {
  it('renders the username and password inputs', () => {
    renderWithAuth(<Login onBack={noop} onSuccess={noop} onNavigateRegister={noop} />);
    expect(screen.getByPlaceholderText('Your username')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument();
  });

  it('renders a Sign In button', () => {
    renderWithAuth(<Login onBack={noop} onSuccess={noop} onNavigateRegister={noop} />);
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('calls onSuccess after successful login', async () => {
    mockFetchSuccess();
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    renderWithAuth(<Login onBack={noop} onSuccess={onSuccess} onNavigateRegister={noop} />);

    await user.type(screen.getByPlaceholderText('Your username'), 'traveler');
    await user.type(screen.getByPlaceholderText('••••••••'), 'securepass123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it('shows an error message when login fails', async () => {
    mockFetchFailure();
    const user = userEvent.setup();

    renderWithAuth(<Login onBack={noop} onSuccess={noop} onNavigateRegister={noop} />);

    await user.type(screen.getByPlaceholderText('Your username'), 'baduser');
    await user.type(screen.getByPlaceholderText('••••••••'), 'wrongpass');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
    );
  });

  it('calls onBack when the Back button is clicked', async () => {
    const onBack = vi.fn();
    const user = userEvent.setup();

    renderWithAuth(<Login onBack={onBack} onSuccess={noop} onNavigateRegister={noop} />);

    await user.click(screen.getByRole('button', { name: /back/i }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('calls onNavigateRegister when "Create one" link is clicked', async () => {
    const onNavigateRegister = vi.fn();
    const user = userEvent.setup();

    renderWithAuth(<Login onBack={noop} onSuccess={noop} onNavigateRegister={onNavigateRegister} />);

    await user.click(screen.getByRole('button', { name: /create one/i }));
    expect(onNavigateRegister).toHaveBeenCalledTimes(1);
  });

  it('disables the submit button while loading', async () => {
    // Keep the fetch pending (never resolves) so the loading state stays active
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    const user = userEvent.setup();

    renderWithAuth(<Login onBack={noop} onSuccess={noop} onNavigateRegister={noop} />);

    await user.type(screen.getByPlaceholderText('Your username'), 'traveler');
    await user.type(screen.getByPlaceholderText('••••••••'), 'pass');

    // Click submit before loading starts (button shows "Sign In" at this point)
    const submitBtn = document.querySelector('button[type="submit"]') as HTMLButtonElement;
    await user.click(submitBtn);

    // Once loading, button is disabled (spinner shown, text "Sign In" gone)
    await waitFor(() =>
      expect(document.querySelector('button[type="submit"]')).toBeDisabled()
    );
  });
});

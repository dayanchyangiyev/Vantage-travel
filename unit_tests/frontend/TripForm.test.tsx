/**
 * TripForm.test.tsx — Unit tests for the TripForm component.
 *
 * TripForm is a pure controlled form component. It uses GeoAutocomplete
 * internally (which calls a GeoNames API). We mock that child component
 * with vi.mock so we can control it without network calls.
 *
 * Tests:
 *   ✓ Renders travel date inputs
 *   ✓ Renders travelers number input with default of 1
 *   ✓ Renders all 7 interest toggle buttons
 *   ✓ Confirm button is disabled when required fields are empty
 *   ✓ Toggling an interest button selects/deselects it
 *   ✓ Changing date inputs updates the form state
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TripForm from '../../src/components/TripForm';
import { noop } from './test_utils';


// ---------------------------------------------------------------------------
// Mock GeoAutocomplete
//
// GeoAutocomplete calls the GeoNames API on every keystroke. In tests, we
// replace it with a simple <input> that forwards the value and onChange.
// ---------------------------------------------------------------------------
vi.mock('../../src/components/GeoAutocomplete', () => ({
  default: ({ id, placeholder, value, onChange }: any) => (
    <input
      id={id}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));


// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TripForm component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders start and end date inputs', () => {
    render(<TripForm onSubmit={noop} />);
    // Check by id since date inputs don't have accessible roles
    expect(document.getElementById('start-date-input')).toBeInTheDocument();
    expect(document.getElementById('end-date-input')).toBeInTheDocument();
  });

  it('renders travelers input with default value of 1', () => {
    render(<TripForm onSubmit={noop} />);
    const input = document.getElementById('travelers-input') as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.value).toBe('1');
  });

  it('renders all 7 interest toggle buttons', () => {
    render(<TripForm onSubmit={noop} />);
    const interests = ['Food', 'Art', 'History', 'Nature', 'Nightlife', 'Shopping', 'Adventure'];
    for (const interest of interests) {
      expect(screen.getByRole('button', { name: interest })).toBeInTheDocument();
    }
  });

  it('confirm button is disabled when required fields are empty', () => {
    render(<TripForm onSubmit={noop} />);
    expect(screen.getByRole('button', { name: /confirm requirements/i })).toBeDisabled();
  });

  it('toggles an interest on and then off', async () => {
    const user = userEvent.setup();
    render(<TripForm onSubmit={noop} />);

    const foodBtn = screen.getByRole('button', { name: 'Food' });
    // Not selected initially
    expect(foodBtn.className).not.toContain('bg-zinc-950');

    // Click once — select it
    await user.click(foodBtn);
    expect(foodBtn.className).toContain('bg-zinc-950');

    // Click again — deselect it
    await user.click(foodBtn);
    expect(foodBtn.className).not.toContain('bg-zinc-950');
  });

  it('updates travelers count when input changes', async () => {
    const user = userEvent.setup();
    render(<TripForm onSubmit={noop} />);

    const travelersInput = document.getElementById('travelers-input') as HTMLInputElement;
    // Use fireEvent for number inputs to set value directly (avoids append issues)
    fireEvent.change(travelersInput, { target: { value: '3' } });
    expect(travelersInput.value).toBe('3');
  });

  it('enables confirm button when all required fields are filled', async () => {
    const user = userEvent.setup();
    render(<TripForm onSubmit={noop} />);

    // Fill departure (via mocked GeoAutocomplete)
    await user.type(screen.getByPlaceholderText('Major city of departure'), 'New York');
    // Fill destination
    await user.type(screen.getByPlaceholderText('Destination city, country'), 'Paris');

    // Fill dates
    const startInput = document.getElementById('start-date-input') as HTMLInputElement;
    const endInput = document.getElementById('end-date-input') as HTMLInputElement;
    await user.type(startInput, '2025-09-01');
    await user.type(endInput, '2025-09-08');

    expect(screen.getByRole('button', { name: /confirm requirements/i })).not.toBeDisabled();
  });

  it('calls onSubmit with form data when confirm button is clicked', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<TripForm onSubmit={onSubmit} />);

    await user.type(screen.getByPlaceholderText('Major city of departure'), 'NYC');
    await user.type(screen.getByPlaceholderText('Destination city, country'), 'Paris');

    const startInput = document.getElementById('start-date-input') as HTMLInputElement;
    const endInput = document.getElementById('end-date-input') as HTMLInputElement;
    await user.type(startInput, '2025-09-01');
    await user.type(endInput, '2025-09-08');

    await user.click(screen.getByRole('button', { name: /confirm requirements/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const callArg = onSubmit.mock.calls[0][0];
    expect(callArg.destination).toBe('Paris');
    expect(callArg.originCountry).toBe('NYC');
  });
});

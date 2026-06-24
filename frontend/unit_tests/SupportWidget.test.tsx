/**
 * SupportWidget.test.tsx — the floating support widget: opening starts a session,
 * a message can surface a policy-gated operation, and confirming executes it.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SupportWidget from '../src/components/SupportWidget';

const startSupportSession = vi.fn();
const sendSupportMessage = vi.fn();
const confirmOperation = vi.fn();
const declineOperation = vi.fn();

vi.mock('../src/lib/support', () => ({
  startSupportSession: (...a: unknown[]) => startSupportSession(...a),
  sendSupportMessage: (...a: unknown[]) => sendSupportMessage(...a),
  confirmOperation: (...a: unknown[]) => confirmOperation(...a),
  declineOperation: (...a: unknown[]) => declineOperation(...a),
}));

describe('SupportWidget', () => {
  beforeEach(() => {
    startSupportSession.mockReset();
    sendSupportMessage.mockReset();
    confirmOperation.mockReset();
    declineOperation.mockReset();
  });

  it('prompts unauthenticated users to sign in', async () => {
    render(<SupportWidget token={null} isAuthenticated={false} onLogin={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Open customer support'));
    expect(await screen.findByText('Sign in')).toBeInTheDocument();
    expect(startSupportSession).not.toHaveBeenCalled();
  });

  it('starts a session, proposes a refund, and confirms it', async () => {
    startSupportSession.mockResolvedValue({ id: 1, mode: 'assist', messages: [], operations: [] });
    render(<SupportWidget token="tok" isAuthenticated onLogin={vi.fn()} />);

    fireEvent.click(screen.getByLabelText('Open customer support'));
    expect(await screen.findByText(/your Vantage support agent/i)).toBeInTheDocument();
    expect(startSupportSession).toHaveBeenCalledTimes(1);

    sendSupportMessage.mockResolvedValue({
      id: 1, mode: 'individual',
      messages: [{ id: 10, role: 'assistant', content: 'I can refund that — please confirm.' }],
      operations: [],
      pending_operation: {
        id: 5, kind: 'refund', status: 'awaiting_confirmation',
        booking_reference: 'VTG-ABC123', policy_basis: 'R1–R4',
      },
    });
    fireEvent.change(screen.getByPlaceholderText('Describe your issue…'), {
      target: { value: 'refund my hotel please' },
    });
    fireEvent.click(screen.getByLabelText('Send message'));

    expect(await screen.findByText('I can refund that — please confirm.')).toBeInTheDocument();
    expect(screen.getByText(/Confirm refund/i)).toBeInTheDocument();
    expect(screen.getByText('VTG-ABC123')).toBeInTheDocument();

    confirmOperation.mockResolvedValue({
      id: 5, status: 'executed', result: { ok: true, message: 'Booking VTG-ABC123 has been refunded.' },
    });
    fireEvent.click(screen.getByText('Confirm'));
    expect(await screen.findByText('Booking VTG-ABC123 has been refunded.')).toBeInTheDocument();
    expect(confirmOperation).toHaveBeenCalledWith('tok', 5);
  });
});

/**
 * Checkout.test.tsx — Unit tests for the mock booking/payment flow.
 *
 * No network is involved (the checkout is a self-contained client-side mock).
 * We verify the order summary, per-step validation, and the happy path through
 * to a confirmation with a booking reference.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Checkout from '../src/components/Checkout';
import { BookingTripContext } from '../src/components/BookingSearch';

const bookHotel = vi.fn();
vi.mock('../src/lib/search', () => ({
  bookHotel: (...args: unknown[]) => bookHotel(...args),
}));

const trip: BookingTripContext = {
  origin: 'New York',
  destinationCity: 'Rome',
  destinationCountry: 'Italy',
  startDate: '2026-09-10',
  endDate: '2026-09-13',
  travelers: 2,
};

const flight = {
  id: 'f1', airline: 'TAP', price: 440, currency: 'USD', stops: 1,
  duration_minutes: 540, departure_time: '', arrival_time: '',
  origin: 'NYC', destination: 'ROM', provider: 'X',
};
const hotel = {
  id: 'h1', name: 'Romoli Hotel', price: 300, currency: 'USD', nights: 3,
  stars: 3, rating: 8.1, board_name: 'Room Only', refundable: true, thumbnail: '', address: 'Via A',
};

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function renderCheckout(onBack = vi.fn()) {
  render(<Checkout trip={trip} selectedFlight={flight} selectedHotel={hotel} onBack={onBack} />);
}

function fillValidDetails() {
  fill('Title', 'Mr');
  fill('First name', 'John');
  fill('Last name', 'Traveler');
  fill('Date of birth', '1990-05-15');
  fill('Gender', 'Male');
  fill('Nationality', 'United States');
  fill('Email', 'john@example.com');
  fill('Phone', '5551234567');
  fill('Passport number', 'X1234567');
  fill('Passport expiry (MM/YY)', '0830');
}

describe('Checkout', () => {
  beforeEach(() => bookHotel.mockReset());

  it('shows the order summary with selected items and a total incl. taxes', () => {
    renderCheckout();
    expect(screen.getByText('TAP')).toBeInTheDocument();
    expect(screen.getByText('Romoli Hotel')).toBeInTheDocument();
    // 440 + 300 + 11% tax (81.40) = 821.40
    expect(screen.getByText('$821.40')).toBeInTheDocument();
  });

  it('blocks progression to payment when details are invalid', () => {
    renderCheckout();
    fireEvent.click(screen.getByText('Continue to Payment'));
    // Still on the details step (payment heading not shown) + an error appears.
    expect(screen.queryByText('Payment Details')).not.toBeInTheDocument();
    expect(screen.getByText('Enter a valid first name')).toBeInTheDocument();
  });

  it('advances to payment, rejects a bad card, then books via the API', async () => {
    bookHotel.mockResolvedValue({
      booking_id: 'BK7FqBgJ', supplier_booking_id: 'BK7FqBgJ', status: 'CONFIRMED',
      hotel_confirmation_code: 'HC123', price: 300, currency: 'USD',
    });
    renderCheckout();
    fillValidDetails();
    fireEvent.click(screen.getByText('Continue to Payment'));

    expect(await screen.findByText('Payment Details')).toBeInTheDocument();

    // Invalid card number → error, no booking call.
    fill('Card number', '1111 1111 1111 1111');
    fill('Name on card', 'John Traveler');
    fill('Expiry (MM/YY)', '1228');
    fill('CVC', '123');
    fill('Billing postal code', '10001');
    fireEvent.click(screen.getByText(/Pay \$/));
    expect(screen.getByText('Enter a valid card number')).toBeInTheDocument();
    expect(bookHotel).not.toHaveBeenCalled();

    // Valid Visa test number → real booking call → confirmation.
    fill('Card number', '4242 4242 4242 4242');
    fireEvent.click(screen.getByText(/Pay \$/));

    expect(await screen.findByText('Booking Confirmed', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(bookHotel).toHaveBeenCalledWith(expect.objectContaining({ offerId: 'h1', email: 'john@example.com' }));
    expect(screen.getByText('BK7FqBgJ')).toBeInTheDocument();
    expect(screen.getByText('HC123')).toBeInTheDocument();
    expect(screen.getByText(/Nuitee Connect/i)).toBeInTheDocument();
  });

});

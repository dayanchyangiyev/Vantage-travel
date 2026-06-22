/**
 * BookingSearch.test.tsx — Unit tests for the BookingSearch component.
 *
 * The lib/search façade is mocked so no network calls are made. We verify the
 * component auto-searches on mount, renders tier-grouped options, and fires the
 * select callback when an option card is clicked.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BookingSearch, { BookingTripContext } from '../src/components/BookingSearch';

const searchFlights = vi.fn();
const searchHotels = vi.fn();

vi.mock('../src/lib/search', () => ({
  searchFlights: (...args: unknown[]) => searchFlights(...args),
  searchHotels: (...args: unknown[]) => searchHotels(...args),
}));

const trip: BookingTripContext = {
  origin: 'New York',
  destinationCity: 'Rome',
  destinationCountry: 'Italy',
  startDate: '2026-09-10',
  endDate: '2026-09-13',
  travelers: 1,
};

const FLIGHTS = {
  origin: 'NYC',
  destination: 'ROM',
  currency: 'USD',
  tiers: {
    cheapest: [{
      id: 'f1', airline: 'TAP', price: 437.75, currency: 'USD', stops: 1,
      duration_minutes: 540, departure_time: '2026-09-10T23:00:00',
      arrival_time: '2026-09-11T12:00:00', origin: 'NYC', destination: 'ROM', provider: 'X',
    }],
    affordable: [],
    moderate: [],
    luxury: [{
      id: 'f2', airline: 'Delta', price: 980, currency: 'USD', stops: 0,
      duration_minutes: 500, departure_time: '2026-09-10T10:00:00',
      arrival_time: '2026-09-10T22:00:00', origin: 'NYC', destination: 'ROM', provider: 'X',
    }],
  },
};

const HOTELS = {
  destination_city: 'Rome',
  destination_country: 'Italy',
  currency: 'USD',
  nights: 3,
  tiers: {
    cheapest: [{
      id: 'h1', name: 'Romoli Hotel', price: 291.83, currency: 'USD', nights: 3,
      stars: 3, rating: 8.1, board_name: 'Room Only', refundable: true, thumbnail: '', address: 'Via A',
    }],
    affordable: [], moderate: [], luxury: [],
  },
};

describe('BookingSearch (flights)', () => {
  beforeEach(() => {
    searchFlights.mockReset();
    searchHotels.mockReset();
  });

  it('auto-searches on mount and renders flight options grouped by tier', async () => {
    searchFlights.mockResolvedValue(FLIGHTS);
    render(<BookingSearch mode="flight" trip={trip} onSelectFlight={vi.fn()} />);

    expect(searchFlights).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('TAP')).toBeInTheDocument();
    expect(screen.getByText('Cheapest')).toBeInTheDocument();
    expect(screen.getByText('Luxury')).toBeInTheDocument();
  });

  it('fires onSelectFlight when an option is clicked', async () => {
    searchFlights.mockResolvedValue(FLIGHTS);
    const onSelectFlight = vi.fn();
    render(<BookingSearch mode="flight" trip={trip} onSelectFlight={onSelectFlight} />);

    const card = await screen.findByText('TAP');
    fireEvent.click(card);
    expect(onSelectFlight).toHaveBeenCalledWith(expect.objectContaining({ id: 'f1', airline: 'TAP' }));
  });

  it('shows an error message when the search fails', async () => {
    searchFlights.mockRejectedValue(new Error('No flight options'));
    render(<BookingSearch mode="flight" trip={trip} onSelectFlight={vi.fn()} />);
    expect(await screen.findByText('No flight options')).toBeInTheDocument();
  });
});

describe('BookingSearch (hotels)', () => {
  beforeEach(() => {
    searchFlights.mockReset();
    searchHotels.mockReset();
  });

  it('renders hotel options and fires onSelectHotel', async () => {
    searchHotels.mockResolvedValue(HOTELS);
    const onSelectHotel = vi.fn();
    render(<BookingSearch mode="hotel" trip={trip} onSelectHotel={onSelectHotel} />);

    expect(searchHotels).toHaveBeenCalledTimes(1);
    const card = await screen.findByText('Romoli Hotel');
    fireEvent.click(card);
    expect(onSelectHotel).toHaveBeenCalledWith(expect.objectContaining({ id: 'h1', name: 'Romoli Hotel' }));
  });
});

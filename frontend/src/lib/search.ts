import {
  CategorizedFlightOptions,
  CategorizedHotelOptions,
  FlightOption,
  HotelOption,
  SavedTrip,
} from "../types/trip";

const API_BASE = "http://127.0.0.1:8000/api";

export interface FlightSearchParams {
  originCity: string;
  destinationCity: string;
  departureDate: string;
  returnDate: string;
  adults: number;
  currency?: string;
}

export interface HotelSearchParams {
  destinationCity: string;
  destinationCountry: string;
  checkIn: string;
  checkOut: string;
  adults: number;
  currency?: string;
}

async function getJson<T>(
  url: string,
  fallbackError: string,
  headers?: Record<string, string>
): Promise<T> {
  const response = await fetch(url, headers ? { headers } : undefined);
  if (!response.ok) {
    let detail = fallbackError;
    try {
      const data = await response.json();
      detail = data?.detail || detail;
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function searchFlights(
  params: FlightSearchParams
): Promise<CategorizedFlightOptions> {
  const query = new URLSearchParams({
    origin_city: params.originCity,
    destination_city: params.destinationCity,
    departure_date: params.departureDate,
    return_date: params.returnDate,
    adults: String(params.adults),
    currency: params.currency || "USD",
  });
  return getJson<CategorizedFlightOptions>(
    `${API_BASE}/trips/flights/search/?${query.toString()}`,
    "Failed to search flights."
  );
}

export async function searchHotels(
  params: HotelSearchParams
): Promise<CategorizedHotelOptions> {
  const query = new URLSearchParams({
    destination_city: params.destinationCity,
    destination_country: params.destinationCountry,
    check_in: params.checkIn,
    check_out: params.checkOut,
    adults: String(params.adults),
    currency: params.currency || "USD",
  });
  return getJson<CategorizedHotelOptions>(
    `${API_BASE}/trips/hotels/search/?${query.toString()}`,
    "Failed to search hotels."
  );
}

export interface HotelBookingParams {
  offerId: string;
  firstName: string;
  lastName: string;
  email: string;
}

export interface BookingConfirmation {
  booking_id: string;
  supplier_booking_id: string | null;
  status: string;
  hotel_confirmation_code: string | null;
  price: number | null;
  currency: string | null;
}

export interface BookingParams {
  kind: "flight" | "hotel";
  offerId: string;
  firstName: string;
  lastName: string;
  email: string;
  title?: string;
  airline?: string;
  price?: number | null;
  currency?: string;
}

/** Normalized result whether the booking was persisted (auth) or a demo. */
export interface BookingResult {
  reference: string;
  status: string;
  hotelConfirmationCode: string | null;
  isReal: boolean;
  alreadyBooked: boolean;
}

/**
 * Create a booking. Hotels book for REAL against the LiteAPI (Nuitee) sandbox
 * (test-only, no charge, appears in Nuitee Connect); flights are recorded as a
 * demo confirmation. When a token is supplied the booking is persisted to the
 * user's account and is idempotent (the same offer is never booked twice).
 */
export async function createBooking(
  params: BookingParams,
  token?: string | null
): Promise<BookingResult> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}/trips/bookings/`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      kind: params.kind,
      offer_id: params.offerId,
      first_name: params.firstName,
      last_name: params.lastName,
      email: params.email,
      title: params.title || "",
      airline: params.airline || "",
      price: params.price ?? null,
      currency: params.currency || "USD",
    }),
  });
  if (!response.ok) {
    let detail = "Booking could not be completed.";
    try {
      const data = await response.json();
      detail = data?.detail || detail;
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }
  const data = await response.json();
  // Persisted bookings (auth) return the Booking row; anonymous returns the raw confirmation.
  return {
    reference: data.reference || data.booking_id,
    status: data.status || "CONFIRMED",
    hotelConfirmationCode:
      data.hotel_confirmation_code ?? data.details?.confirmation?.hotel_confirmation_code ?? null,
    isReal: data.is_real ?? params.kind === "hotel",
    alreadyBooked: data.already_booked ?? false,
  };
}

export interface BookingRecord {
  id: number;
  kind: "flight" | "hotel";
  offer_id: string;
  reference: string;
  status: string;
  title: string;
  price: number | null;
  currency: string;
  is_real: boolean;
  created_at: string;
}

/** List the authenticated user's bookings. */
export async function listBookings(token: string): Promise<BookingRecord[]> {
  return getJson<BookingRecord[]>(`${API_BASE}/trips/bookings/`, "Failed to load bookings.", {
    Authorization: `Bearer ${token}`,
  });
}

/**
 * Persist the chosen flight and/or hotel onto a saved trip.
 * Only meaningful for authenticated users with a saved trip id.
 */
export async function saveSelection(
  token: string,
  tripId: number,
  selection: { selected_flight?: FlightOption | null; selected_hotel?: HotelOption | null }
): Promise<SavedTrip> {
  const response = await fetch(`${API_BASE}/trips/${tripId}/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(selection),
  });
  if (!response.ok) {
    throw new Error("Failed to save your selection.");
  }
  return response.json();
}

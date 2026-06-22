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

async function getJson<T>(url: string, fallbackError: string): Promise<T> {
  const response = await fetch(url);
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

/**
 * Create a REAL booking against the LiteAPI (Nuitee) sandbox. The sandbox key is
 * test-only — no money is charged — but the booking appears in Nuitee Connect.
 */
export async function bookHotel(params: HotelBookingParams): Promise<BookingConfirmation> {
  const response = await fetch(`${API_BASE}/trips/bookings/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      offer_id: params.offerId,
      first_name: params.firstName,
      last_name: params.lastName,
      email: params.email,
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
  return response.json();
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

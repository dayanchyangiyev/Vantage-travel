import { DynamicTierQuote } from "../types/trip";

const API_BASE = "http://127.0.0.1:8000/api";

export interface DynamicTierParams {
  originCity: string;
  destinationCity: string;
  destinationCountry: string;
  departureDate: string;
  returnDate: string;
  adults: number;
  currency?: string;
}

export async function fetchDynamicTierQuote(
  params: DynamicTierParams
): Promise<DynamicTierQuote> {
  const query = new URLSearchParams({
    origin_city: params.originCity,
    destination_city: params.destinationCity,
    destination_country: params.destinationCountry,
    departure_date: params.departureDate,
    return_date: params.returnDate,
    adults: String(params.adults),
    currency: params.currency || "USD",
  });

  const response = await fetch(`${API_BASE}/trips/budget/tiers/?${query.toString()}`);
  if (!response.ok) {
    let detail = "Failed to fetch dynamic pricing.";
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

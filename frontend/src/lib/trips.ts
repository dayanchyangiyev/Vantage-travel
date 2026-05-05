import { SavedTrip, TripInput, TripPlan } from "../types/trip";

const API_BASE = "http://127.0.0.1:8000/api";

export async function fetchCurrentTrip(token: string): Promise<SavedTrip | null> {
  const response = await fetch(`${API_BASE}/trips/current/`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error("Failed to load saved trip");
  }

  return response.json();
}

export async function saveTrip(
  token: string,
  input: TripInput,
  plan: TripPlan
): Promise<SavedTrip> {
  const response = await fetch(`${API_BASE}/trips/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      origin_country: input.originCountry,
      destination: input.destination,
      travelers: input.travelers,
      start_date: input.startDate,
      end_date: input.endDate,
      budget_profile: input.budget,
      interests: input.interests,
      engine_output: plan,
      pricing_snapshot: input.pricingSnapshot || {},
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to save trip preferences");
  }

  return response.json();
}

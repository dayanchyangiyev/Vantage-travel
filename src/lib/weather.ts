import { WeatherSummary } from '../types/trip';

const API_BASE = 'http://127.0.0.1:8000/api';

export interface WeatherParams {
  destinationCity: string;
  destinationCountry: string;
  startDate?: string;
  endDate?: string;
}

export async function fetchWeatherSummary(params: WeatherParams): Promise<WeatherSummary> {
  const queryObj: Record<string, string> = {
    destination_city: params.destinationCity,
    destination_country: params.destinationCountry,
  };
  if (params.startDate) queryObj.start_date = params.startDate;
  if (params.endDate) queryObj.end_date = params.endDate;
  const query = new URLSearchParams(queryObj);
  const response = await fetch(`${API_BASE}/trips/weather/?${query.toString()}`);
  if (!response.ok) {
    let detail = 'Failed to fetch weather data.';
    try {
      const data = await response.json();
      detail = data?.detail || detail;
    } catch {
      // keep default
    }
    throw new Error(detail);
  }
  return response.json();
}

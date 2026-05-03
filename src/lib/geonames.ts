const API_BASE = 'http://127.0.0.1:8000/api';

export interface GeoName {
  geonameId: number;
  name: string;
  toponymName: string;
  countryName?: string;
  countryCode?: string;
  population: number;
  lat: string;
  lng: string;
  fcode: string;
  adminName1?: string;
}

export async function searchGeoNames(
  query: string,
  type: 'country' | 'destination'
): Promise<GeoName[]> {
  if (query.length < 2) return [];

  const params = new URLSearchParams({ q: query, type });

  try {
    const res = await fetch(`${API_BASE}/trips/geonames/?${params}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.geonames ?? [];
  } catch {
    return [];
  }
}

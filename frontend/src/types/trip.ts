export interface TripInput {
  originCountry: string;
  destination: string;
  budget: 'cheapest' | 'affordable' | 'moderate' | 'luxury';
  travelers: number;
  startDate: string;
  endDate: string;
  interests: string[];
  pricingSnapshot?: DynamicTierQuote | null;
}

export interface SavedTrip {
  id: number;
  user: number;
  origin_country: string;
  destination: string;
  travelers: number;
  start_date: string;
  end_date: string;
  budget_profile: 'cheapest' | 'affordable' | 'moderate' | 'luxury';
  interests: string[];
  engine_output: TripPlan;
  pricing_snapshot?: DynamicTierQuote | Record<string, unknown>;
  selected_flight?: FlightOption | null;
  selected_hotel?: HotelOption | null;
  created_at: string;
  updated_at: string;
}

export type TierKey = 'cheapest' | 'affordable' | 'moderate' | 'luxury';

export interface FlightOption {
  id: string;
  airline: string;
  price: number;
  currency: string;
  stops: number;
  duration_minutes: number;
  departure_time: string;
  arrival_time: string;
  origin: string;
  destination: string;
  provider: string;
}

export interface HotelOption {
  id: string;
  name: string;
  price: number;
  currency: string;
  nights: number;
  stars: number;
  rating: number;
  board_name: string;
  refundable: boolean;
  thumbnail: string;
  address: string;
}

export interface CategorizedFlightOptions {
  origin: string;
  destination: string;
  currency: string;
  tiers: Record<TierKey, FlightOption[]>;
}

export interface CategorizedHotelOptions {
  destination_city: string;
  destination_country: string;
  currency: string;
  nights: number;
  tiers: Record<TierKey, HotelOption[]>;
}

export interface DynamicTierBreakdown {
  flight_cost: number;
  hotel_daily_cost: number;
  local_daily_cost: number;
  total_daily_living_cost: number;
  total_living_cost: number;
  total_trip_cost: number;
}

export interface DynamicTierQuote {
  destination_city: string;
  destination_country: string;
  trip_duration_days: number;
  currency: string;
  tiers: Record<'cheapest' | 'affordable' | 'moderate' | 'luxury', DynamicTierBreakdown>;
  sources: {
    flights: string;
    hotels: string;
    local_costs: string;
  };
}

export interface TicketInfo {
  price: string;
  company: string;
  pros: string[];
  cons: string[];
  tips: string;
}

export interface BudgetCalculation {
  min: string;
  medium: string;
  comfortable: string;
  luxury: string;
  hotelInfo: string;
  foodInfo: string;
}

export interface WeatherSummary {
  condition: string;
  high_c: number;
  low_c: number;
  high_f: number;
  low_f: number;
  humidity_pct: number;
  precipitation_pct: number;
  date_label: string;
  is_forecast: boolean;
}

export interface TripPlan {
  bestTimeToTravel: {
    period: string;
    reason: string;
    weather: string;
    touristDensity: 'low' | 'high';
  };
  tickets: TicketInfo[];
  budget: BudgetCalculation;
  events: { name: string; date: string; description: string }[];
  places: { name: string; type: 'historical' | 'interesting'; description: string }[];
  tips: string[];
  facts: string[];
}

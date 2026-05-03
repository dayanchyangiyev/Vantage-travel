export interface TripInput {
  originCountry: string;
  destination: string;
  budget: 'cheapest' | 'affordable' | 'moderate' | 'luxury';
  travelers: number;
  startDate: string;
  endDate: string;
  interests: string[];
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
  created_at: string;
  updated_at: string;
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

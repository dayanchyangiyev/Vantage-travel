import { TripInput, TripPlan } from "../types/trip";

export async function generateTripPlan(input: TripInput): Promise<TripPlan> {
  // Mocking the engine as requested
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        bestTimeToTravel: {
          period: "September - October",
          reason: "Mild temperatures and fewer crowds make this the optimal window for exploration.",
          weather: "22°C Clear",
          touristDensity: "low",
        },
        tickets: [
          {
            price: "$450",
            company: "Premier Air",
            pros: ["Direct flight", "Modern fleet"],
            cons: ["Limited baggage"],
            tips: "Book at least 3 weeks in advance for this rate."
          },
          {
            price: "$320",
            company: "Global Link",
            pros: ["Affordable", "Frequent departures"],
            cons: ["1 stopover", "Older aircraft"],
            tips: "Check-in early to avoid seat separation."
          }
        ],
        budget: {
          min: "$1,200",
          medium: "$2,800",
          comfortable: "$4,500",
          luxury: "$12,000",
          hotelInfo: "Budget stays are found in the northern district, while luxury options center around the historic plaza.",
          foodInfo: "Local markets offer high-quality dining for minimal cost."
        },
        events: [
          { name: "Annual Light Festival", date: "Oct 12", description: "City-wide illumination event." },
          { name: "Harvest Market", date: "Every Sunday", description: "Local artisanal products and food." }
        ],
        places: [
          { name: "The Old Observatory", type: "historical", description: "Pristine viewpoints from the 18th century." },
          { name: "Modernist Gallery", type: "interesting", description: "A cutting-edge collection of local contemporary art." }
        ],
        tips: ["Pack light", "Use the public transit pass", "Carry a reusable water bottle"],
        facts: ["The city was founded on seven hills", "It produces 40% of the region's silk"]
      });
    }, 1500);
  });
}

export async function chatWithAgent(message: string, context?: TripPlan): Promise<string> {
  return "This is a mock response from the Vantage interface. The backend engine connection is pending.";
}

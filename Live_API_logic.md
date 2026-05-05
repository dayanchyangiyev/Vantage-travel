# Live API Logic (Step-by-Step)

## 1) What You Need To Do (Setup Actions)

1. Open `.env/.env` and fill these values:
- `SERPAPI_API_KEY=...`
- `GOOGLE_PLACES_TEXT_SEARCH_URL=...` (default: `https://places.googleapis.com/v1/places:searchText`)
- `GOOGLE_PLACES_API_KEY=...`

2. Keep this for SerpAPI endpoint:
- `SERPAPI_BASE_URL=https://serpapi.com/search.json`

3. Install dependencies:
- `pip install -r requirements.txt`

4. Check backend config:
- `env/bin/python backend/manage.py check`

5. Start backend:
- `env/bin/python backend/manage.py runserver`

6. Start frontend:
- `npm run dev`

7. In UI, fill trip input:
- Departure city
- Destination city
- Destination country
- Departure and return dates
- Travelers

8. Wait for dynamic tier cards (`cheapest`, `affordable`, `moderate`, `luxury`) to load.

9. Select a tier and continue.

---

## 2) Runtime Flow (How Backend Works)

### A) Dynamic Pricing Fetch Flow

1. User selects destination + dates + travelers.

2. Frontend triggers:
- `GET /api/trips/budget/tiers/`

3. Backend view receives request:
- `trips/views.py -> budget_country_tiers`

4. Backend creates a pricing input object and calls service layer:
- `trips/services.py -> build_dynamic_tier_quotes(...)`

5. Service fetches **flight prices** from SerpAPI Google Flights:
- Resolve origin and destination to airport IATA codes
- Request Google Flights search results
- Extract numeric flight prices from result sections

6. Service fetches **hotel prices** from SerpAPI Google Hotels:
- Search hotels by destination city/country and stay dates
- Extract nightly hotel prices from property results

7. Service fetches **local living costs** from Google Places Text Search:
- Queries `restaurants`, `cafes`, and `public transport` for the destination city
- Reads `places[].priceLevel` and `places[].priceRange` (when available)
- Maps `priceLevel` enums to coefficients and converts to numeric amounts
- Computes deterministic daily values for each tier (`cheapest`..`luxury`)

8. Service applies tiering algorithm to each source:
- Sort numeric values
- Map into 4 categories:
  - `cheapest`
  - `affordable`
  - `moderate`
  - `luxury`

9. Service computes per-tier totals:
- `flight_cost`
- `hotel_daily_cost`
- `local_daily_cost`
- `total_daily_living_cost`
- `total_living_cost`
- `total_trip_cost`

10. Backend returns payload with all category numbers.

11. Frontend displays category cards with values and lets user choose.

---

### B) Feasibility Evaluation Flow

1. User submits selected category and budgets.

2. Frontend calls:
- `POST /api/trips/budget/evaluate/`

3. Backend validates input and recomputes dynamic tier snapshot.

4. Backend evaluates if selected tier is feasible with:
- user `total_living_budget`
- trip duration

5. Backend returns:
- `feasible: true/false`
- metrics
- warning (if needed)
- optimized duration suggestion (if infeasible)

---

## 3) Where Logic Lives in Code

- Service layer (all provider calls + tier math):
  - `backend/trips/services.py`

- API endpoints:
  - `backend/trips/views.py`

- Input validation:
  - `backend/trips/serializers.py`

- Routes:
  - `backend/trips/urls.py`

- Env config:
  - `backend/backend/settings.py`

- Frontend dynamic pricing UI:
  - `src/components/TripForm.tsx`
  - `src/lib/dynamicPricing.ts`

---

## 4) Conceptual Summary (Simple)

- Destination/date/travelers are the trigger.
- Backend calls live APIs.
- Backend filters and classifies real prices into 4 tiers.
- Backend sends those values to UI.
- User chooses a tier.
- Backend checks if user budget can support that tier.
- Backend returns feasibility and recommendation.

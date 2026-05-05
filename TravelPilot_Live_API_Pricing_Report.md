# TravelPilot Live API Pricing Engine - Implementation Report

## Overview
Implemented a fully dynamic pricing architecture for TravelPilot where category values are computed at runtime from external provider data instead of fixed country constants.

The new flow is:
1. User selects trip inputs (origin, destination, dates, travelers).
2. Backend fetches:
   - Flights from **SerpAPI**
   - Hotels from **SerpAPI Google Hotels**
   - Local living cost data from **Google Places Text Search**
3. Backend filters/prioritizes provider results and computes four categories:
   - `cheapest`, `affordable`, `moderate`, `luxury`
4. Frontend shows computed numeric values per category before confirmation.

No hardcoded per-country budget values remain in the engine.

---

## Backend Changes

### 1) Replaced deterministic mock-cost engine with live provider architecture
**File:** `backend/trips/services.py` (replaced)

Added a provider-driven service layer with:
- `SerpApiFlightProvider`
  - Location-to-IATA resolution from SerpAPI autocomplete
  - Google Flights results retrieval
  - Extraction of real flight prices
- `SerpApiHotelProvider`
  - Google Hotels results retrieval by city/country and dates
  - Extraction of numeric hotel pricing candidates
- `LocalCostProvider`
  - Google Places Text Search integration (`places[]` payload)
  - Uses `priceLevel` + `priceRange` (Money) to derive numeric local-cost points
  - Rule-based daily tier approximation for `cheapest/affordable/moderate/luxury`

Added category computation strategy:
- Prices are sorted and mapped to tiers by percentile-centered window averaging:
  - `cheapest`: 15th percentile
  - `affordable`: 40th percentile
  - `moderate`: 60th percentile
  - `luxury`: 90th percentile
- For each tier, the algorithm takes a window of **20 to 30 prices** around the tier percentile and computes the **mean average**.
- If fewer than 20 prices exist, it uses all available prices for the mean.
- Source independence is preserved:
  - `flight_cost` mean is computed from flight offers only
  - `hotel_daily_cost` mean is computed from hotel offers only (converted to per-day first)
  - `local_daily_cost` mean is computed from local-cost API values only

This defines a dynamic and consistent 4-tier filter strategy without hardcoded country cost tables.

Added budget feasibility evaluation on top of dynamic tiers:
- Uses selected category's dynamic living daily cost
- Computes shortfall and optimized duration when infeasible

---

### 2) Updated serializers for dynamic API contract
**File:** `backend/trips/serializers.py`

`BudgetTierQuerySerializer` now validates:
- `origin_city`
- `destination_city`
- `destination_country`
- `departure_date`
- `return_date`
- `adults`
- `currency`

`BudgetEvaluationInputSerializer` now validates:
- same trip/search fields above
- `max_flight_budget`
- `total_living_budget`
- `comfort_preference`

---

### 3) Updated views to use dynamic providers and category engine
**File:** `backend/trips/views.py`

`GET /api/trips/budget/tiers/`
- Now executes runtime provider pipeline and returns full dynamic tier breakdown (flight + hotel + local + totals).

`POST /api/trips/budget/evaluate/`
- Now evaluates feasibility using the dynamic tier snapshot generated from live provider data.

Existing trip persistence and geonames endpoints were preserved.

---

### 4) Updated trips routes
**File:** `backend/trips/urls.py`

Kept budget routes but with upgraded behavior:
- `GET /api/trips/budget/tiers/`
- `POST /api/trips/budget/evaluate/`

---

### 5) Added provider credentials/config to settings via `.env`
**File:** `backend/backend/settings.py`

Added decouple-loaded settings:
- `SERPAPI_BASE_URL`
- `SERPAPI_API_KEY`
- `GOOGLE_PLACES_TEXT_SEARCH_URL`
- `GOOGLE_PLACES_API_KEY`

---

### 6) Added new keys in env file
**File:** `.env/.env`

Added placeholders for all dynamic pricing providers listed above.

---

## Frontend Changes

### 1) Added dynamic quote data types
**File:** `src/types/trip.ts`

Added:
- `DynamicTierBreakdown`
- `DynamicTierQuote`

---

### 2) Added API client for dynamic tier fetching
**File:** `src/lib/dynamicPricing.ts` (new)

Added `fetchDynamicTierQuote(...)` which calls:
- `GET /api/trips/budget/tiers/`

---

### 3) Optimized trip form UI for dynamic category pricing
**File:** `src/components/TripForm.tsx`

Enhancements:
- Two-step flow:
  - Step 1: user chooses route + dates + travelers
  - Step 2: user chooses interests and dynamic budget category
- Debounced fetch of dynamic category quote in Step 2
- Loading/error states for pricing fetch
- Displays 4 pricing cards with runtime numeric values:
  - Flight cost
  - Hotel/day
  - Local/day
  - Trip total
- Shows explicit formula next to category totals:
  - `Flight + (Hotel/day + Local/day) * NumberOfDays`
- User can directly choose category from these dynamic cards

This aligns the interface with the required flow:
- choose destination -> fetch prices -> calculate categories -> show values -> user selects category.

---

## Category Filtering Strategy (Core Requirement)
The four categories are defined by algorithmic filtering of fetched provider prices (not fixed constants):

1. Collect candidate numeric values from each source.
2. Sort ascending.
3. For each tier percentile (`15%`, `40%`, `65%`, `90%`):
- find percentile center index in sorted prices
- take a centered window of **20-30 values** (as available)
- compute the **mean average of that window**
- use that mean as the tier value
4. Combine source tiers into final category outputs:
- `flight_cost`
- `hotel_daily_cost`
- `local_daily_cost`
- computed living + trip totals

This means tier values are not a single random point; they are smoothed, statistically stable averages from each percentile zone.

---

## API Response Behavior (Runtime)
`GET /api/trips/budget/tiers/` now returns:
- destination/currency/duration metadata
- `tiers.cheapest|affordable|moderate|luxury`
  - `flight_cost`
  - `hotel_daily_cost`
  - `local_daily_cost`
  - `total_daily_living_cost`
  - `total_living_cost`
  - `total_trip_cost`
- `sources` metadata

`POST /api/trips/budget/evaluate/` returns:
- feasibility
- shortfall metrics
- optimized duration suggestion
- embedded dynamic pricing snapshot

---

## Verification Performed
- `python manage.py check` -> passed
- `npm run build` -> passed

Note:
- `npm run lint` fails due TypeScript scanning files in `env/lib/python...` (existing project config scope issue, not introduced by this change).

---

## Files Created / Modified

### Created
- `backend/trips/services.py`
- `src/lib/dynamicPricing.ts`
- `TravelPilot_Live_API_Pricing_Report.md`

### Modified
- `backend/trips/serializers.py`
- `backend/trips/views.py`
- `backend/trips/urls.py`
- `backend/backend/settings.py`
- `.env/.env`
- `src/components/TripForm.tsx`
- `src/types/trip.ts`

---

## How to Enable with Real Keys
Set these in `.env/.env`:
- `SERPAPI_API_KEY`, `SERPAPI_BASE_URL`
- `GOOGLE_PLACES_TEXT_SEARCH_URL`, `GOOGLE_PLACES_API_KEY`

After keys are configured, dynamic tier computation will operate against live provider data for selected routes/dates.

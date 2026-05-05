# Backend Minimal Test Report: Bucharest -> Frankfurt

## Test Date
- May 5, 2026

## Scope
- Run a minimal backend integration test for:
  - Departure city: `Bucharest`
  - Destination city: `Frankfurt`
  - Destination country: `Germany`
- Validate live provider flow:
  - SerpAPI flights
  - SerpAPI hotels
  - RapidAPI local cost of living
- Keep requests minimal.

## Test Input
- `departure_date`: `2026-06-10`
- `return_date`: `2026-06-17`
- `adults`: `1`
- `currency`: `USD`
- `comfort_preference`: `affordable`
- `max_flight_budget`: `500`
- `total_living_budget`: `900`

## Minimal Request Strategy Used
- Flights: used known IATA codes (`OTP` -> `FRA`) to avoid autocomplete requests.
- Flights now use segmented queries by travel class (`economy`, `premium economy`, `business`, `first`) and stops filter.
- Hotels now use segmented queries by hotel class/rating (`2-3`, `3-4`, `4`, `5` stars).
- Local costs: one RapidAPI query for `Frankfurt, Germany`.

## Live Fetch Results

### 1) Flights (SerpAPI Google Flights)
- Status: success
- Segmented tier fetch status: success
- Computed tier values from fetched dataset:
  - `cheapest` (15th): `294.33`
  - `affordable` (40th): `323.03`
  - `moderate` (60th): `474.47`
  - `luxury` (90th): `1616.60`

### 2) Hotels (SerpAPI Google Hotels)
- Status: success
- Segmented tier fetch status: success
- Computed tier values from fetched dataset:
  - `cheapest` (15th): `66.2`
  - `affordable` (40th): `87.0`
  - `moderate` (60th): `126.2`
  - `luxury` (90th): `320.0`

### 3) Local Daily Costs (RapidAPI Cost of Living and Prices)
- Status: failed
- Failure from backend flow:
  - `HTTPError 429: Too Many Requests`
- Meaning:
  - provider or subscription rate limit was reached at request time.

## Backend Output Result (for requested route)

### `build_dynamic_tier_quotes(...)`
- Did not complete because local cost provider failed.
- Failure point: `LocalCostProvider.fetch_daily_tier_costs(...)`

### `evaluate_dynamic_budget(...)`
- Not produced, because it depends on successful `build_dynamic_tier_quotes(...)`.

## Working vs Not Working

### Working
- SerpAPI flight fetch pipeline
- SerpAPI hotel fetch pipeline
- Tier computation now returns distinct values per category percentile for flights and hotels, using different filtered datasets per tier.

### Not Working
- RapidAPI Cost of Living endpoint for this run (HTTP 429 rate limiting)
- End-to-end quote and feasibility response for this route, because local daily costs are mandatory

## Conclusion
- The backend integration is **partially working**.
- Flight and hotel data fetching is operational for `Bucharest -> Frankfurt`.
- Full trip pricing is currently blocked by RapidAPI local-cost availability for this run (`HTTP 429`).

## Update: Local-Cost-Only Recheck (Google Places)
- Run date: May 5, 2026
- Scope: only local daily living expenses (no flight/hotel checks).
- Query target: `Frankfurt, Germany`
- Currency: `USD`
- Provider: `Google Places Text Search`

### Output
- `cheapest`: `41.3217`
- `affordable`: `50.8667`
- `moderate`: `75.9717`
- `luxury`: `115.2333`

### Status
- Local daily living cost calculation is working with Google Places API.
- Tier values are increasing correctly by category and can be used directly in trip total calculation.

## Next Steps: Caching / Saving System (So You Don’t Fetch Every Time)

### 1) Add cache keys by query signature
- Build deterministic keys:
  - Flights key: `flight:{origin}:{destination}:{departure}:{return}:{adults}:{currency}`
  - Hotels key: `hotel:{city}:{country}:{checkin}:{checkout}:{adults}:{currency}`
  - Local costs key: `local:{city}:{country}:{currency}`

### 2) Use Django cache backend
- Start with local memory or file cache for development.
- Move to Redis in production.
- Read cache first; call API only on miss.

### 3) Set provider-specific TTLs
- Flights TTL: 6-12 hours.
- Hotels TTL: 6-12 hours.
- Local cost TTL: 3-7 days (changes slower).

### 4) Cache both raw and normalized data
- Raw payload cache for audit/debug.
- Normalized numeric arrays/tier results cache for fast API responses.

### 5) Add database persistence for historical snapshots
- New model `PricingSnapshot`:
  - query fields (route, dates, travelers, currency)
  - provider raw hashes
  - computed tiers
  - `fetched_at`, `expires_at`
- Lets you reuse old snapshots and show historical pricing to users.

### 6) Add stale-while-revalidate flow
- If cache is expired but available:
  - return stale snapshot immediately,
  - trigger background refresh (Celery/cron) to update cache.
- Keeps UI responsive under rate limits.

### 7) Add rate-limit fallback behavior
- If provider returns 429/5xx:
  - return last known cached snapshot if exists,
  - return clear `source_status` metadata (`fresh`, `stale`, `unavailable`).

### 8) Add endpoint metadata for transparency
- Include in API response:
  - `cache_hit` boolean per source,
  - `fetched_at`,
  - `expires_at`,
  - provider error details if partial failure.

### 9) Implement a scheduled warm-up job
- Pre-fetch popular routes/cities daily.
- Reduces cold starts and user-facing wait times.

### 10) Add tests for cache correctness
- Miss -> fetch -> store -> hit flow.
- Expired cache -> stale fallback flow.
- Provider 429 -> cached snapshot fallback flow.

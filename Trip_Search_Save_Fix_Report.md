# Trip Search & Save Fix Report

## Date
May 3, 2026

## Goal
Fix two production blockers:
1. City/country autocomplete returns too many options.
2. Trip form could not proceed/save, and users could not reliably persist preferences.

## Root Causes Found

### 1) Form submit was blocked by a nonexistent field
In `src/components/TripForm.tsx`, the submit button used this condition:
- `!formData.originCity`

`originCity` does not exist in `TripInput` or form state. This kept the submit button disabled, so the app never reached the save API call.

### 2) Search endpoint returned broad place sets (and could return empty)
`backend/trips/views.py` used GeoNames population ordering but still broad place results. Also, if upstream GeoNames provided no usable results, the frontend got no suggestions.

### 3) UI displayed a non-schema field
`src/components/Dashboard.tsx` rendered `savedTrip.origin_city`, but this field is not in the backend model/serializer response.

## What I Changed

### A) Unblocked trip submission and saving
**File:** `src/components/TripForm.tsx`
- Removed invalid `originCity` from submit disabling logic.
- New submit condition only checks real fields:
  - `originCountry`, `destination`, `startDate`, `endDate`.

Result: user can now submit the form, trigger planning, and save via API.

### B) Limited search results to major cities only
**File:** `backend/trips/views.py`
- Increased GeoNames fetch pool to 50 raw records, then filtered server-side.
- For destination search, now only keeps major cities:
  - Feature codes: `PPLC`, `PPLA`, `PPLA2`, or `PPL` with population >= 200,000.
- Hard-limited returned suggestions to 8 items.

Result: significantly narrower, major-city-focused suggestions.

### C) Added resilient fallback for autocomplete
**File:** `backend/trips/views.py`
- Added curated major-city fallback list used when GeoNames returns no usable entries or fails.
- Fallback is query-filtered and capped to 8 results.

Result: autocomplete remains functional even when external API is unavailable/rate-limited.

### D) Cleaned inconsistent saved-preferences UI
**File:** `src/components/Dashboard.tsx`
- Removed display of `origin_city` (not present in saved schema).

Result: dashboard now reflects actual persisted fields only.

### E) Corrected settings env usage
**File:** `backend/backend/settings.py`
- Changed `GOOGLE_MAPS_API_KEY` to read from proper env key name.
- Changed `GEONAMES_USERNAME` to env-driven with default fallback.

Result: configuration is safer and easier to manage by environment.

## How API Data Is Fetched and Saved

## 1. Autocomplete fetch flow
1. User types in departure/destination field.
2. `GeoAutocomplete` debounces input and calls `searchGeoNames()`.
3. `searchGeoNames()` calls:
   - `GET /api/trips/geonames/?q=<query>&type=destination`
4. Backend `geonames_search`:
   - Calls GeoNames
   - Filters to major cities only
   - Falls back to curated major-city list when needed
5. Frontend shows up to 8 suggestions.

## 2. Save flow (preferences + generated trip)
1. User submits `TripForm`.
2. `App.handleStartTrip()` generates plan via `generateTripPlan()`.
3. If authenticated, frontend calls `saveTrip()`:
   - `POST /api/trips/`
   - payload includes `origin_country`, `destination`, dates, travelers, budget, interests, `engine_output`.
4. Backend `TripListCreateView.perform_create()` attaches logged-in user and saves through `TripSerializer`.
5. DB row is created in `Trip` table.
6. Frontend stores returned saved record in state (`savedTrip`).

## 3. Load saved preferences flow
1. On authenticated app load, frontend calls `fetchCurrentTrip()`:
   - `GET /api/trips/current/`
2. Backend `CurrentTripView` returns most recent user trip.
3. Frontend uses this for:
   - Continue Previous Trip flow
   - Prefill data when starting a new search form.

## Verification Performed

### Django checks
- `env/bin/python backend/manage.py check`
- Result: passed (no issues).

### Search API behavior check
- Called `GET /api/trips/geonames/?q=lo&type=destination`.
- Result sample (major-city style):
  - London, United Kingdom
  - Los Angeles, United States
  - Sao Paulo, Brazil

### Save-to-database check
Using authenticated DRF test client:
- `POST /api/trips/` returned `201`.
- `GET /api/trips/current/` returned `200`.
- Database row count increased by 1 for the user during test.

### Frontend build
- `npm run build` passed successfully.

## Files Modified For This Fix
- `backend/trips/views.py`
- `backend/backend/settings.py`
- `src/components/TripForm.tsx`
- `src/components/Dashboard.tsx`
- `Trip_Search_Save_Fix_Report.md` (this report)

## Current Outcome
- Users can proceed from the form and save trip data.
- Saved data is written to DB for authenticated users.
- Autocomplete is constrained to major-city-style results with fallback resilience.
- Saved preferences view is aligned with actual backend schema.

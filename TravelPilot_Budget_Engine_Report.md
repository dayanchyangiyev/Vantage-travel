# TravelPilot Budget Engine - Implementation Report

## 1) Summary
Implemented a deterministic, fully local budget engine in the Django `trips` app with no external live API dependency.

The implementation includes:
- A dedicated **service layer** (`services.py`) for core budget logic.
- A local **mock cost registry** (Python dictionary) keyed by `destination_country`.
- A runtime endpoint to fetch daily tier costs for UI toggles.
- A runtime endpoint to evaluate budget feasibility and optimization suggestions.
- Input validation via DRF serializers.

This architecture is decoupled and ready for future replacement of local registry with live wrappers controlled via `.env` configuration.

---

## 2) What Was Implemented

### A. Core Service Layer (Deterministic Engine)
**Created:** `backend/trips/services.py`

Added:
- `COUNTRY_DAILY_COSTS`: local mock registry with four tiers per country.
- `BudgetInput` dataclass for typed service input.
- Typed response contracts via `TypedDict`:
  - `BudgetMetrics`
  - `BudgetSuggestions`
  - `BudgetEvaluationResult`
- `get_country_tier_costs(destination_country)`:
  - Returns all four daily cost values for dynamic UI display.
- `get_tier_daily_cost(destination_country, comfort_preference)`:
  - Returns selected tier daily cost with validation.
- `evaluate_budget_feasibility(input_data)`:
  - Applies deterministic math:
    - `C_required = D * P_tier`
    - `A_available = total_living_budget / D`
    - If infeasible:
      - `daily_shortfall = P_tier - A_available`
      - `total_shortfall = daily_shortfall * D`
      - `D_suggested = floor(total_living_budget / P_tier)`
  - Returns JSON-compatible dictionary matching requested output shape.

Notes:
- Uses `Decimal` for financial calculations and stable arithmetic.
- Includes strong validation (non-negative budgets, duration > 0, supported country/tier).

---

### B. Request Validation Layer
**Modified:** `backend/trips/serializers.py`

Added:
- `BudgetTierQuerySerializer`:
  - Validates `destination_country` query param.
- `BudgetEvaluationInputSerializer`:
  - Validates payload fields:
    - `destination_country`
    - `trip_duration_days` (>=1)
    - `max_flight_budget` (>=0)
    - `total_living_budget` (>=0)
    - `comfort_preference` in allowed choices

---

### C. API Endpoints
**Modified:** `backend/trips/views.py`

Added endpoints:
1. `budget_country_tiers` (`GET`)
   - Input: `destination_country` as query parameter
   - Output: daily costs for all four tiers
   - Purpose: dynamic frontend toggle updates

2. `evaluate_budget` (`POST`)
   - Input: full budget payload
   - Calls `services.evaluate_budget_feasibility(...)`
   - Output: deterministic feasibility response with metrics and suggestions

No external live APIs are used by these budget endpoints.

---

### D. URL Routing
**Modified:** `backend/trips/urls.py`

Added routes:
- `GET /api/trips/budget/tiers/`
- `POST /api/trips/budget/evaluate/`

---

## 3) Files Created / Modified

### Created
- `backend/trips/services.py`
- `TravelPilot_Budget_Engine_Report.md`

### Modified
- `backend/trips/serializers.py`
- `backend/trips/views.py`
- `backend/trips/urls.py`

---

## 4) How It Works (Runtime Flow)

### 4.1 Dynamic Tier Lookup (UI Toggle)
1. Frontend calls:
   - `GET /api/trips/budget/tiers/?destination_country=France`
2. Backend validates request.
3. Service loads `France` from local registry.
4. Response returns:
   - `cheapest`, `affordable`, `moderate`, `luxury` daily amounts.

### 4.2 Feasibility Evaluation
1. Frontend submits payload to:
   - `POST /api/trips/budget/evaluate/`
2. Backend validates payload and types.
3. Service computes costs and feasibility.
4. Response returns:
- `feasible`
- `metrics` (selected daily cost, daily allowance, expected total cost, shortfall)
- `warnings`
- `suggestions` (optimized duration, message)

---

## 5) Example Validation (Requested Scenario)
Tested scenario:
- destination_country: `France`
- trip_duration_days: `7`
- max_flight_budget: `500`
- total_living_budget: `1000`
- comfort_preference: `moderate` (`$160/day`)

Observed response:
- `feasible: false`
- `total_expected_ground_cost: 1120.0`
- `total_shortfall: 120.0`
- `optimized_duration_days: 6`

This matches the expected optimization behavior.

---

## 6) Verification Performed
- `python manage.py check` -> passed
- API smoke tests via DRF test client:
  - `GET /api/trips/budget/tiers/` -> 200, correct daily costs
  - `POST /api/trips/budget/evaluate/` -> 200, correct infeasible result and suggestion

---

## 7) Decoupling & Future API Swap Strategy
Current design intentionally isolates decision logic in `services.py`.

To switch from local mock data to live providers later:
- Replace `COUNTRY_DAILY_COSTS` lookup with a provider interface (adapter/wrapper).
- Keep endpoint contracts unchanged.
- Select provider implementation using `.env` flags/config.

This keeps frontend contracts stable while backend data source evolves.

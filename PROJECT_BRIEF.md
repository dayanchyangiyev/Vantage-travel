# Vantage Travel — AI Agent Project Brief

> **READ THIS FIRST.** This document is a complete briefing for any AI agent working on this project.
> It covers the current state, architecture, files, patterns, and strict development rules.
> Do not make assumptions — use only what is described here.

---

## 0. Current Situation (Latest) — READ THIS

The pricing/search stack was migrated off **SerpAPI** onto **LiteAPI (a.k.a.
Nuitee Connect / `connect.nuitee`)** for both flights and hotels, and a
flight/hotel **search + selection** feature was added.

**What changed most recently:**
1. **Flight & hotel search (LiteAPI).** Users can search individual, selectable
   flight and hotel options on the dashboard, grouped into the 4 tiers
   (`cheapest/affordable/moderate/luxury`), 2–3 options per tier, plus a dedicated
   full-screen search tab for each. The chosen flight/hotel is **saved on the Trip**
   (selection only — **no booking or payment**).
2. **SerpAPI removed.** `SerpApiClient`, `SerpApiFlightProvider`,
   `SerpApiHotelProvider` and all `SERPAPI_*` settings/env are gone. The 4-tier
   budget (`build_dynamic_tier_quotes`) is now derived from the **LiteAPI flight +
   hotel search prices**.
3. **`LocalCostProvider` (Google Places food costs) removed.** Daily "living" cost
   is now **derived from the fetched nightly lodging price** per tier
   (`_living_daily_cost`, with per-tier factor/floor/cap). Google Places is still
   used, but **only for weather geocoding** (`GoogleWeatherProvider`).
4. **Dashboard "Transit Protocols" section removed** (the Gemini `plan.tickets`
   block). `TripPlan.tickets` still exists in the type but is no longer rendered.
5. **Mock checkout/booking flow added** (`components/Checkout.tsx`, step
   `"checkout"`). A "Book & Pay" button on the dashboard (enabled once a flight
   and/or hotel is selected) opens a multi-step wizard: traveler details →
   payment → confirmation, with client-side validation (Luhn card check, card-brand
   detection, expiry/age checks), a simulated processing delay, and a generated
   booking reference. **Entirely a front-end mock — no real charge, no backend
   endpoint, nothing persisted.** For the university demo.

**Key external-API facts (verified against the LiteAPI sandbox):**
- Base `https://api.liteapi.travel/v3.0`, auth header `X-API-Key`, sandbox key
  prefix `sand_`. Env vars: `NUITEE_API_KEY`, `NUITEE_PUBLIC_KEY`, `NUITEE_BASE_URL`.
- Hotels: `POST /hotels/rates` with `aiSearch:"City, Country"` (avoids needing
  ISO-2 codes); hotel names/stars/photo from `GET /data/hotels?hotelIds=<csv>`.
- Flights: `POST /flights/rates` with `legs[]`; resolve city→IATA via
  `GET /data/flights/airports?q=<city>` (prefer the metro "All Airports" code —
  a single airport can return far fewer routes).
- **Latency note:** LiteAPI sandbox flight/hotel calls take ~4–6s each (supplier
  aggregation). `build_dynamic_tier_quotes` runs the two searches concurrently
  (`ThreadPoolExecutor`) so the budget loads in ~5–6s, in parallel with Gemini/weather.

**Test counts:** 137 backend (`pytest`) + 33 frontend (`vitest`).

The sections below are the stable architecture/rules. Where an older section still
says "SerpAPI" or "Google Places for local costs," **this section 0 overrides it.**

---

## 1. What This Project Is

**Vantage Travel** is a full-stack travel planning web application. A user types in a destination, travel dates, and number of travelers. The app:

1. Queries **LiteAPI (Nuitee)** for real, selectable **flight options** across the four budget tiers
2. Queries **LiteAPI (Nuitee)** for real, selectable **hotel options** across the four budget tiers
3. Derives a 4-tier **trip budget** from those LiteAPI flight + hotel prices (daily living cost is inferred from lodging price)
4. Sends the inputs to **Google Gemini AI** to generate a full written trip plan (itinerary, tips, packing list)
5. Lets the user **choose and save a specific flight + hotel**, plus save the trip and revisit it later
6. Provides a **budget evaluation** tool: user inputs their max budget, app tells them if it's feasible and suggests adjustments

The four pricing tiers used throughout are always: `cheapest`, `affordable`, `moderate`, `luxury`.

---

## 2. Tech Stack

### Backend
| Component | Technology |
|---|---|
| Language | Python 3.14 |
| Framework | Django 6.x |
| API layer | Django REST Framework (DRF) |
| Authentication | JWT via `djangorestframework-simplejwt` |
| Database | SQLite (file: `databases/user_data.sqlite`) |
| Config | `python-decouple` reads from `.env/.env` |
| Test runner | `pytest` + `pytest-django` + `pytest-mock` + `factory_boy` |

### Frontend
| Component | Technology |
|---|---|
| Language | TypeScript |
| Framework | React 18 |
| Build tool | Vite |
| Styling | Tailwind CSS (utility classes, no custom CSS files) |
| Animation | Framer Motion (`motion/react`) |
| Icons | Lucide React |
| HTTP | Native `fetch()` — no Axios or other library |
| Test runner | Vitest + @testing-library/react + jsdom |

### External APIs
| API | Purpose | Key env var |
|---|---|---|
| LiteAPI (Nuitee Connect) | Flight + hotel search/options + 4-tier budget basis | `NUITEE_API_KEY` (`NUITEE_PUBLIC_KEY`, `NUITEE_BASE_URL`) |
| Google Places | Weather geocoding only (city → lat/lng) | `GOOGLE_PLACES_API_KEY` |
| Google Weather | Destination weather summary | `GOOGLE_WEATHER_API_KEY` |
| GeoNames | City autocomplete in the form | `GEONAMES_USERNAME` |
| Google Gemini | AI trip plan generation | Handled in `src/lib/gemini.ts` |

> **Removed:** SerpAPI (flights/hotels) and Google Places "local daily living
> costs" are no longer used. Living cost is derived from LiteAPI lodging prices.

---

## 3. Project Directory Structure

```
Vantage-travel/
│
├── backend/                        ← Django project root
│   ├── backend/                    ← Django project config package
│   │   ├── settings.py             ← Main settings (reads from .env/.env)
│   │   ├── test_settings.py        ← Test-only settings (fixed key, in-memory SQLite)
│   │   └── urls.py                 ← Root URL config
│   ├── trips/                      ← Primary Django app
│   │   ├── models.py               ← Trip model (the only custom model)
│   │   ├── serializers.py          ← DRF serializers (input validation / DTO layer)
│   │   ├── views.py                ← API endpoint handlers (thin controllers)
│   │   ├── services.py             ← ALL business logic (900 lines, never touch from views)
│   │   ├── api_logging.py          ← Passive logging of all external API calls
│   │   └── urls.py                 ← trips app URL routes
│   ├── accounts/                   ← Auth Django app
│   │   ├── models.py               ← No custom model — uses Django's built-in User
│   │   ├── serializers.py          ← RegisterSerializer
│   │   ├── views.py                ← RegisterView, ProfileView
│   │   └── urls.py                 ← accounts URL routes
│   ├── conftest.py                 ← Root conftest (Django boot for pytest)
│   └── pytest.ini                  ← Pytest config (points to test_settings)
│
├── src/                            ← React frontend source
│   ├── App.tsx                     ← Root component + state machine (step)
│   ├── context/
│   │   └── AuthContext.tsx         ← JWT auth state (Context/Provider pattern)
│   ├── components/
│   │   ├── Login.tsx               ← Login form
│   │   ├── Register.tsx            ← Registration form
│   │   ├── TripForm.tsx            ← Trip input form (destination, dates, interests)
│   │   ├── Dashboard.tsx           ← Trip results + "Flights & Stays" search/selection section
│   │   ├── BookingSearch.tsx       ← Reusable flight/hotel search UI (embedded + full variants)
│   │   ├── Checkout.tsx            ← Mock multi-step booking/payment wizard (demo only)
│   │   └── GeoAutocomplete.tsx     ← City autocomplete input (calls GeoNames)
│   ├── lib/
│   │   ├── trips.ts                ← Façade: fetch/save trip via backend API
│   │   ├── dynamicPricing.ts       ← Façade: fetch 4-tier budget via backend API
│   │   ├── search.ts               ← Façade: flight/hotel search + saveSelection (PATCH)
│   │   ├── gemini.ts               ← Façade: generate trip plan via Gemini
│   │   └── geonames.ts             ← Façade: city search via GeoNames
│   └── types/
│       └── trip.ts                 ← All TypeScript interfaces (TripInput, DynamicTierQuote, etc.)
│
├── unit_tests/                     ← All test files (never import into production code)
│   ├── backend/
│   │   ├── conftest.py             ← Django setup + shared fixtures
│   │   ├── test_models.py
│   │   ├── test_serializers.py
│   │   ├── test_services_helpers.py
│   │   ├── test_services_nuitee.py        ← LiteAPI flight/hotel providers + bucketing
│   │   ├── test_services_orchestration.py ← build_dynamic_tier_quotes + evaluate_dynamic_budget
│   │   ├── test_services_weather.py
│   │   ├── test_views_trips.py
│   │   ├── test_views_search.py           ← flight/hotel search + trip selection PATCH
│   │   └── test_views_accounts.py
│   │   (removed: test_services_flights.py, test_services_hotels.py, test_services_local_costs.py)
│   └── frontend/
│       ├── setup.ts                ← jest-dom + localStorage mock + cleanup
│       ├── test_utils.tsx          ← renderWithAuth helper
│       ├── Login.test.tsx
│       ├── Register.test.tsx
│       └── TripForm.test.tsx
│
├── databases/
│   ├── .gitkeep
│   └── user_data.sqlite            ← Dev database (gitignored)
│
├── logs/
│   └── api_responses/              ← Auto-generated JSONL logs per provider per day
│
├── .env/
│   └── .env                        ← All secrets (gitignored — never commit this)
│
├── requirements.txt                ← Python dependencies
├── package.json                    ← Node dependencies + test/dev scripts
├── vite.config.ts                  ← Vite + Vitest config
├── DESIGN_PATTERNS.md              ← Detailed pattern explanations
├── TESTING_GUIDE.md                ← How to run tests + what each test covers
└── PROJECT_BRIEF.md                ← This file
```

---

## 4. Backend API Endpoints

All routes are prefixed with `http://127.0.0.1:8000/api/`

### Accounts (`/api/accounts/`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `accounts/register/` | None | Create new user |
| POST | `accounts/login/` | None | Returns JWT access + refresh tokens |
| POST | `accounts/login/refresh/` | None | Refresh access token |
| GET | `accounts/profile/` | Bearer JWT | Get current user info |

### Trips (`/api/trips/`)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `trips/` | Bearer JWT | List user's trips |
| POST | `trips/` | Bearer JWT | Create/save a trip |
| GET/PATCH | `trips/<id>/` | Bearer JWT | Retrieve/update a trip — used to PATCH `selected_flight`/`selected_hotel` |
| GET | `trips/current/` | Bearer JWT | Get most recent saved trip |
| GET | `trips/geonames/` | None | City autocomplete proxy |
| GET | `trips/flights/search/` | None | LiteAPI flight options grouped into 4 tiers |
| GET | `trips/hotels/search/` | None | LiteAPI hotel options grouped into 4 tiers |
| GET | `trips/budget/tiers/` | None | 4-tier pricing breakdown (LiteAPI-derived) |
| POST | `trips/budget/evaluate/` | None | Check if budget is feasible |
| GET | `trips/weather/` | None | Destination weather summary |

---

## 5. Data Model

### Trip (the only custom model)
```
Trip
├── user            ForeignKey(User) — owner
├── origin_country  CharField — departure city
├── destination     CharField — "City, Country" format
├── travelers       PositiveIntegerField — minimum 1
├── start_date      DateField
├── end_date        DateField — must be >= start_date (enforced in clean())
├── budget_profile  CharField — choices: cheapest/affordable/moderate/luxury
├── interests       JSONField — list of strings e.g. ["Food", "Art"]
├── engine_output   JSONField — Gemini-generated trip plan (stored as dict)
├── pricing_snapshot JSONField — full 4-tier pricing result
├── selected_flight JSONField (null) — chosen LiteAPI flight option (migration 0004)
├── selected_hotel  JSONField (null) — chosen LiteAPI hotel option (migration 0004)
├── created_at      DateTimeField(auto_now_add=True)
└── updated_at      DateTimeField(auto_now=True)

Ordering: -created_at (newest first)
```

No other custom models exist. User auth uses Django's built-in `User` model unchanged.

---

## 6. Frontend Application Flow

The frontend is a Single Page Application with **6 screens** controlled by a single state machine:

```
"landing"  →  "form"     →  "loading"  →  "dashboard"
"landing"  →  "login"    →  "landing"
"landing"  →  "register" →  "login"
```

State is managed in `App.tsx` with `const [step, setStep] = useState<Step>("landing")`.

On mount, `App.tsx` checks if the user is authenticated and tries to load their most recent saved trip. If a trip with a saved `engine_output` exists, the app goes directly to `"dashboard"`.

---

## 7. Services Architecture (The Core — Read Carefully)

`backend/trips/services.py` contains ALL business logic. It is never called directly from URLs — only from `views.py`.

### Key classes and functions:

**`LiteApiClient`** — wraps all HTTP calls to LiteAPI (Nuitee). Handles URL building, `X-API-Key` header injection, and routes every call through `_http_request_json()` (so logging/redaction is automatic). `post(path, payload)` / `get(path, params)`.

**`NuiteeFlightProvider`** — resolves city→IATA (`/data/flights/airports?q=`), calls `POST /flights/rates` with round-trip `legs[]`, maps journeys → `FlightOption`s (airline, price, stops, duration, times), dedupes, and buckets into 4 tiers via `_bucket_options_by_price()`. `search_options(FlightSearchInput) → CategorizedFlightResult`.

**`NuiteeHotelProvider`** — calls `POST /hotels/rates` with `aiSearch:"City, Country"`, joins names/stars/photo from `GET /data/hotels?hotelIds=`, maps each hotel's cheapest offer → `HotelOption`, buckets into 4 tiers. `search_options(HotelSearchInput) → CategorizedHotelResult`.

**`search_flight_options()` / `search_hotel_options()`** — thin service entry points the views call (guard `adults > 0`, delegate to the providers).

**`build_dynamic_tier_quotes(input: DynamicPricingInput) → DynamicTierQuoteResult`** — the 4-tier budget orchestrator. Runs `NuiteeFlightProvider` + `NuiteeHotelProvider` **concurrently** (`ThreadPoolExecutor`), takes a representative (cheapest) price per tier (`_representative_tier_prices`, with neighbour-fill), converts hotel stay-totals to nightly, derives daily living via `_living_daily_cost()`, and assembles per-tier totals. Signature/output shape unchanged from the SerpAPI era.

**`GoogleWeatherProvider`** — unchanged; geocodes via Google Places, fetches Google Weather forecast.

**`evaluate_dynamic_budget(input: BudgetEvaluationInput) → BudgetEvaluationResult`** — calls `build_dynamic_tier_quotes` then checks if the user's stated budget covers their preferred tier. Returns feasibility + suggestions.

### Helper functions (pure, no side effects):
- `_safe_decimal(value)` — converts anything to Decimal or None
- `_parse_date(s)` — parses YYYY-MM-DD string to date
- `_coerce_iata_code(s)` — returns uppercase 3-letter code or None
- `_tier_value_from_sorted(values, percentile)` — windowed average at a percentile
- `_map_values_to_tiers(values)` — maps sorted prices to the 4 tier keys
- `_extract_numeric_candidates(data)` — recursively pulls price-like numbers from any dict/list

---

## 8. Design Patterns In Use — Mandatory Reference

These 8 patterns are the established architecture. **All future changes must follow them.**

### Pattern 1: MVC / Client-Server MTV
- **Backend = Model + Controller**: `models.py` defines data, `views.py` handles HTTP routing
- **Frontend = View**: React components only display and collect data, no business logic
- **Rule**: Views never calculate prices. Components never validate business rules. Keep layers strict.

### Pattern 2: Service Layer
- **All business logic lives in `services.py`**. Views call services. Services call providers.
- **Rule**: Never add business logic to `views.py`. Never call external APIs from `views.py`. If a new calculation is needed, add a function to `services.py` and call it from the view.

### Pattern 3: Provider / Strategy
- Each external source is its own class with a consistent interface.
- Current providers: `NuiteeFlightProvider`, `NuiteeHotelProvider` (both expose `search_options(...)`), and `GoogleWeatherProvider`. All HTTP goes through `LiteApiClient`/`_http_request_json`.
- **Rule**: If adding a new data source, create a new `XxxProvider` class that returns options/prices grouped by the 4 tiers (reuse `_bucket_options_by_price()`), and wire it into `build_dynamic_tier_quotes()` if it affects the budget.

### Pattern 4: Façade
- **Backend**: `SerpApiClient` hides raw HTTP. `build_dynamic_tier_quotes()` hides multi-provider orchestration.
- **Frontend**: Every file in `src/lib/` is a Façade. `fetchDynamicTierQuote()`, `saveTrip()`, `fetchCurrentTrip()`, `generateTripPlan()` hide all `fetch()` complexity.
- **Rule**: Components in `src/components/` never call `fetch()` directly. They always go through a function in `src/lib/`. If a new API call is needed, add a new function to `src/lib/`, not inside a component.

### Pattern 5: Data Transfer Object (DTO)
- **Backend**: Input is always validated by a DRF Serializer before reaching `services.py`. Service layer receives a typed dataclass (`DynamicPricingInput`), not a raw dict.
- **Frontend**: All data shapes are defined as TypeScript interfaces in `src/types/trip.ts`.
- **Rule**: Never pass raw JSON dicts between layers. Define the shape first (dataclass or TypeScript interface), then use it. If adding a new endpoint, write the serializer first.

### Pattern 6: Observer (Passive Logging)
- `api_logging.py` has one public function: `log_api_response(...)`. It is called inside `SerpApiClient` and `LocalCostProvider` after every HTTP call.
- **Rule**: `log_api_response()` must be called for every external HTTP call. It auto-redacts API keys. It never raises exceptions. Never log secrets manually elsewhere.

### Pattern 7: Context / Provider (React)
- Auth state (`user`, `token`, `login()`, `logout()`, `isAuthenticated`) is provided globally via `AuthContext.tsx`.
- **Rule**: Never pass `token` or `user` as props down a component tree. Always use `useAuth()`. If new global state is needed (e.g., user preferences), create a new context file following `AuthContext.tsx` as the template.

### Pattern 8: State Machine (React)
- `App.tsx` uses `type Step = "landing" | "login" | "register" | "form" | "dashboard" | "flight-search" | "hotel-search" | "checkout"`. The `flight-search`/`hotel-search` steps render a full-screen `<BookingSearch variant="full" />`; `checkout` renders `<Checkout />`. Selecting an option updates App state and (when authenticated) PATCHes the trip via `saveSelection`.
- **Rule**: If a new screen is added, add its name to the `Step` union type and add a corresponding conditional render block in `App.tsx`. Never show two screens simultaneously. Never use boolean flags (`isLoginOpen`, `isDashboardOpen`) — use the `step` state.

---

## 9. What Must NOT Be Changed

The following are load-bearing parts of the architecture. Do not modify, refactor, or delete these without explicit instruction:

| File / Item | Why it must not change |
|---|---|
| `services.py` function signatures | Tests, views, and orchestration all depend on them |
| `Trip` model fields | Database schema — changing requires migrations |
| `_map_values_to_tiers()` logic | Core pricing algorithm used everywhere |
| `AuthContext.tsx` interface | `useAuth()` is called in Login, App, and future components |
| `src/types/trip.ts` interfaces | TypeScript compile safety across the entire frontend |
| `backend/unit_tests/` and `frontend/unit_tests/` | Tests must stay passing — run them after any change |
| `databases/` path in `settings.py` | Database file location is referenced in `settings.py` and `.gitignore` |
| `.env/.env` structure | All env var names are referenced in `settings.py` via `decouple` |
| `log_api_response()` call sites | Removing them loses the audit trail silently |

---

## 10. Development Rules for New Features

Follow these rules in order for every new feature:

### Adding a new backend endpoint
1. Add the serializer (DTO) to `serializers.py` first — define exactly what input/output looks like
2. Add the business logic function to `services.py` — it receives a typed dataclass, returns a typed dict
3. Add the view to `views.py` — it validates input with the serializer, calls the service, returns Response
4. Register the URL in `trips/urls.py`
5. Write unit tests in `backend/unit_tests/` — mock all external calls

### Adding a new external data source
1. Create a new `XxxProvider` class in `services.py`
2. Follow the same interface as `SerpApiFlightProvider`: one public method, returns `{"cheapest": Decimal, ...}`
3. Use `SerpApiClient` (or a new equivalent) for the HTTP call — never use `requests` directly
4. Call `log_api_response()` after every HTTP call
5. Wire the new provider into `build_dynamic_tier_quotes()` if it contributes to trip pricing
6. Write tests in `backend/unit_tests/test_services_xxx.py` — mock the HTTP layer

### Adding a new frontend screen
1. Create `src/components/NewScreen.tsx`
2. Add `"new-screen"` to the `Step` type in `App.tsx`
3. Add the render block: `{step === "new-screen" && <NewScreen onBack={() => setStep("...")} />}`
4. If it needs an API call, add a function in `src/lib/` first
5. If it needs auth state, use `useAuth()` — never pass token as a prop
6. Write a test in `frontend/unit_tests/NewScreen.test.tsx`

### Adding a new pricing tier or modifying tiers
> ⚠️ The four tiers (`cheapest`, `affordable`, `moderate`, `luxury`) are hardcoded throughout the backend and frontend. Changing them requires updating: `_map_values_to_tiers()`, all TypeScript interfaces in `types/trip.ts`, and `Dashboard.tsx`. This is a large change — proceed carefully.

---

## 11. Environment Setup

### Backend
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
cd backend && python manage.py migrate

# Start dev server
python manage.py runserver
```

### Frontend
```bash
# Install dependencies
npm install

# Start dev server
npm run dev
```

### Environment Variables (`.env/.env`)
```
# DJANGO_SECRET_KEY= (Optional in dev, defaults to insecure key)
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
GEONAMES_USERNAME=<your-geonames-username>
GOOGLE_MAPS_API_KEY=<key>
# LiteAPI / Nuitee Connect (flight + hotel search; sandbox key prefix sand_)
NUITEE_BASE_URL=https://api.liteapi.travel/v3.0
NUITEE_API_KEY=<your-liteapi-key>
NUITEE_PUBLIC_KEY=<your-liteapi-public-key>
# Google Places — used for weather geocoding only
GOOGLE_PLACES_TEXT_SEARCH_URL=https://places.googleapis.com/v1/places:searchText
GOOGLE_PLACES_API_KEY=<your-places-key>
# Google Weather
GOOGLE_WEATHER_BASE_URL=https://weather.googleapis.com/v1/forecast/days:lookup
GOOGLE_WEATHER_API_KEY=<your-weather-key>
```

> SerpAPI env vars (`SERPAPI_*`) have been removed.

---

## 12. Testing

### Run backend tests (167 total — 137 backend, 30 frontend)
```bash
source venv/bin/activate
cd backend && python -m pytest unit_tests/ -v
```

### Run frontend tests
```bash
npm run test
```

### Rules for writing new tests
- **All external HTTP calls must be mocked** — never call real APIs in tests
- Backend: use `mocker.patch("trips.services.XxxProvider.fetch_tier_prices", return_value={...})`
- Frontend: use `vi.stubGlobal('fetch', vi.fn().mockResolvedValue({...}))`
- Use `backend/unit_tests/conftest.py` fixtures: `api_client`, `auth_client`, `test_user`
- Test settings (`backend/backend/test_settings.py`) use in-memory SQLite and a fixed secret key — no `.env` needed to run tests
- New test files go in `backend/unit_tests/` or `frontend/unit_tests/` — never in the app directories

---

## 13. Current Limitations & Known Constraints

- **No real-time updates**: Pricing is fetched once per trip creation. There is no WebSocket or polling.
- **SQLite only**: The database is SQLite. For production, migrate to PostgreSQL by updating `DATABASES` in `settings.py`.
- **Single user per trip**: Each trip belongs to one user. There is no sharing or collaboration.
- **Gemini key**: The Gemini API key for trip plan generation is handled in `src/lib/gemini.ts` on the frontend. For production this should move to the backend.
- **No pagination**: `GET /api/trips/` returns all user trips. Add pagination via DRF's `PageNumberPagination` if the list grows.
- **CORS**: `CORS_ALLOW_ALL_ORIGINS=True` is set for development. In production, restrict this to the deployed frontend domain.

---

## 14. Git Branches

- **`unit-tests`** — current active branch (last commit: full unit test suite, 164 tests)
- The main branch contains the full app before tests were added

---

## 15. Reference Documents

| File | Contents |
|---|---|
| `DESIGN_PATTERNS.md` | Full detailed explanation of all 8 patterns with code examples |
| `TESTING_GUIDE.md` | Plain-English guide to running and writing tests |
| `PROJECT_BRIEF.md` | This file — start here for all future development |

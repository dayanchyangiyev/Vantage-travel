# Vantage Travel — AI Agent Project Brief

> **READ THIS FIRST.** This document is a complete briefing for any AI agent working on this project.
> It covers the current state, architecture, files, patterns, and strict development rules.
> Do not make assumptions — use only what is described here.

---

## 1. What This Project Is

**Vantage Travel** is a full-stack travel planning web application. A user types in a destination, travel dates, and number of travelers. The app:

1. Queries **SerpAPI** (Google Flights) for real flight prices across four budget tiers
2. Queries **SerpAPI** (Google Hotels) for real hotel prices across four budget tiers
3. Queries **Google Places** for local daily living costs (food, activities) across four budget tiers
4. Sends the inputs to **Google Gemini AI** to generate a full written trip plan (itinerary, tips, packing list)
5. Lets the user save the trip and revisit it later
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
| SerpAPI | Flight + hotel prices | `SERPAPI_API_KEY` |
| Google Places | Local daily living costs | `GOOGLE_PLACES_API_KEY` |
| GeoNames | City autocomplete in the form | `GEONAMES_USERNAME` |
| Google Gemini | AI trip plan generation | Handled in `src/lib/gemini.ts` |

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
│   │   ├── Dashboard.tsx           ← Trip results display
│   │   └── GeoAutocomplete.tsx     ← City autocomplete input (calls GeoNames)
│   ├── lib/
│   │   ├── trips.ts                ← Façade: fetch/save trip via backend API
│   │   ├── dynamicPricing.ts       ← Façade: fetch pricing tiers via backend API
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
│   │   ├── test_services_flights.py
│   │   ├── test_services_hotels.py
│   │   ├── test_services_local_costs.py
│   │   ├── test_services_orchestration.py
│   │   ├── test_views_trips.py
│   │   └── test_views_accounts.py
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
| GET | `trips/current/` | Bearer JWT | Get most recent saved trip |
| GET | `trips/geonames/` | None | City autocomplete proxy |
| GET | `trips/budget/tiers/` | None | Get 4-tier pricing breakdown |
| POST | `trips/budget/evaluate/` | None | Check if budget is feasible |

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
└── created_at      DateTimeField(auto_now_add=True)

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

**`SerpApiClient`** — wraps all HTTP calls to SerpAPI. Handles: URL building, API key injection, request execution, response parsing, error handling, and calling `log_api_response()`.

**`SerpApiFlightProvider`** — uses `SerpApiClient` to fetch flight prices, parse the response structure, extract all numeric price candidates, and call `_map_values_to_tiers()`.

**`SerpApiHotelProvider`** — same pattern as flights but for hotels. Parses `rate_per_night`, `extracted_price`, and `ads` sections.

**`LocalCostProvider`** — calls Google Places Text Search API to find restaurants/activities. Uses `priceLevel`, `priceRange`, and `rating` to estimate daily living costs per tier.

**`build_dynamic_tier_quotes(input: DynamicPricingInput) → DynamicTierQuoteResult`** — the main orchestrator. Calls all three providers, assembles the result, calculates total trip cost per tier.

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
- Each external pricing source is its own class with a consistent interface.
- Current providers: `SerpApiFlightProvider`, `SerpApiHotelProvider`, `LocalCostProvider`
- **Rule**: If adding a new data source (e.g., car rentals), create a new `XxxProvider` class with a `fetch_tier_prices()` method that returns `{"cheapest": Decimal, "affordable": Decimal, "moderate": Decimal, "luxury": Decimal}`. Wire it into `build_dynamic_tier_quotes()`.

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
- `App.tsx` uses `type Step = "landing" | "login" | "register" | "form" | "loading" | "dashboard"`.
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
SERPAPI_BASE_URL=https://serpapi.com/search.json
SERPAPI_API_KEY=<your-serpapi-key>
GOOGLE_PLACES_TEXT_SEARCH_URL=https://places.googleapis.com/v1/places:searchText
GOOGLE_PLACES_API_KEY=<your-places-key>
```

---

## 12. Testing

### Run backend tests (164 total — 142 backend, 22 frontend)
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

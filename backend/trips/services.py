from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Any, Dict, List, TypedDict
from urllib.error import HTTPError

from django.conf import settings
from .api_logging import log_api_response


VALID_COMFORT_TIERS = {"cheapest", "affordable", "moderate", "luxury"}
TIER_ORDER = ["cheapest", "affordable", "moderate", "luxury"]
TIER_PERCENTILES = {
    "cheapest": Decimal("0.15"),
    "affordable": Decimal("0.40"),
    "moderate": Decimal("0.60"),
    "luxury": Decimal("0.90"),
}


class TierCostBreakdown(TypedDict):
    flight_cost: float
    hotel_daily_cost: float
    local_daily_cost: float
    total_daily_living_cost: float
    total_living_cost: float
    total_trip_cost: float


class DynamicTierQuoteResult(TypedDict):
    destination_city: str
    destination_country: str
    trip_duration_days: int
    currency: str
    tiers: Dict[str, TierCostBreakdown]
    sources: Dict[str, str]


class BudgetMetrics(TypedDict):
    selected_tier_daily_cost: float
    actual_daily_allowance: float
    total_expected_ground_cost: float
    total_shortfall: float


class BudgetSuggestions(TypedDict):
    optimized_duration_days: int | None
    message: str | None


class BudgetEvaluationResult(TypedDict):
    feasible: bool
    metrics: BudgetMetrics
    warnings: str | None
    suggestions: BudgetSuggestions
    pricing_snapshot: DynamicTierQuoteResult


@dataclass(frozen=True)
class DynamicPricingInput:
    origin_city: str
    destination_city: str
    destination_country: str
    departure_date: str
    return_date: str
    adults: int
    max_flight_budget: Decimal
    total_living_budget: Decimal
    comfort_preference: str
    currency: str = "USD"


def _parse_date(raw_date: str) -> date:
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Dates must use YYYY-MM-DD format.") from exc


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        cleaned = re.sub(r"[^0-9.\-]", "", str(value).replace(",", "").strip())
        if not cleaned:
            return None
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _http_request_json(
    method: str,
    url: str,
    headers: Dict[str, str] | None = None,
    params: Dict[str, Any] | None = None,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    request_url = url
    if params:
        request_url += "?" + urllib.parse.urlencode(params)

    body = None
    effective_headers = headers.copy() if headers else {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        effective_headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(
        request_url,
        data=body,
        headers=effective_headers,
        method=method,
    )
    parsed_url = urllib.parse.urlparse(request_url)
    host = parsed_url.netloc or "unknown"
    provider = host
    if params and params.get("engine"):
        provider = f"{host}:{params.get('engine')}"

    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
            duration_ms = int((time.monotonic() - started) * 1000)
            log_api_response(
                provider=provider,
                method=method,
                url=request_url,
                request_headers=effective_headers,
                request_params=params,
                request_payload=payload,
                status_code=response.getcode(),
                response_body=data,
                duration_ms=duration_ms,
            )
            return data
    except HTTPError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        error_body: Any = None
        try:
            raw_body = exc.read().decode("utf-8", errors="replace")
            try:
                error_body = json.loads(raw_body)
            except json.JSONDecodeError:
                error_body = {"raw": raw_body[:5000]}
        except Exception:
            error_body = None
        log_api_response(
            provider=provider,
            method=method,
            url=request_url,
            request_headers=effective_headers,
            request_params=params,
            request_payload=payload,
            status_code=exc.code,
            response_body=error_body,
            error=str(exc),
            duration_ms=duration_ms,
        )
        raise
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        log_api_response(
            provider=provider,
            method=method,
            url=request_url,
            request_headers=effective_headers,
            request_params=params,
            request_payload=payload,
            status_code=None,
            response_body=None,
            error=str(exc),
            duration_ms=duration_ms,
        )
        raise


def _extract_numeric_candidates(node: Any) -> List[Decimal]:
    values: List[Decimal] = []
    if isinstance(node, dict):
        for key, value in node.items():
            key_lower = key.lower()
            if any(token in key_lower for token in ("price", "rate", "cost", "amount", "fare")):
                parsed = _safe_decimal(value)
                if parsed is not None and parsed > 0:
                    values.append(parsed)
            values.extend(_extract_numeric_candidates(value))
    elif isinstance(node, list):
        for item in node:
            values.extend(_extract_numeric_candidates(item))
    return values


def _tier_value_from_sorted(values: List[Decimal], percentile: Decimal) -> Decimal:
    """
    Compute a deterministic tier value using a percentile-centered window
    and return the mean of that window (not a single picked value).

    Window policy:
    - Prefer a window size between 20 and 30 prices.
    - If fewer than 20 prices are available, use all available prices.
    """
    if not values:
        raise ValueError("Cannot compute tiers from empty value list.")

    total = len(values)
    if total == 1:
        return values[0]

    # Target window: 20-30 values for normal sample sizes.
    # For smaller samples, keep a narrower percentile-centered window
    # so categories do not collapse to the same full-list average.
    if total >= 20:
        window_size = min(30, total)
        window_size = max(20, window_size)
    else:
        if total <= 3:
            window_size = 1
        elif total <= 7:
            window_size = 3
        else:
            window_size = 5

    center_index = int(
        (Decimal(total - 1) * percentile).to_integral_value(rounding=ROUND_FLOOR)
    )

    half = window_size // 2
    start = max(0, center_index - half)
    end = start + window_size
    if end > total:
        end = total
        start = max(0, end - window_size)

    window = values[start:end]
    if not window:
        return values[center_index]

    return sum(window) / Decimal(len(window))


def _map_values_to_tiers(values: List[Decimal]) -> Dict[str, Decimal]:
    sorted_values = sorted(v for v in values if v > 0)
    if not sorted_values:
        raise ValueError("No usable pricing values were returned by provider.")

    return {
        tier: _tier_value_from_sorted(sorted_values, pct)
        for tier, pct in TIER_PERCENTILES.items()
    }


def _coerce_iata_code(city_or_code: str) -> str | None:
    token = city_or_code.strip().upper()
    return token if len(token) == 3 and token.isalpha() else None


class GoogleWeatherProvider:
    def __init__(self):
        self.api_key = getattr(settings, "GOOGLE_WEATHER_API_KEY", "")
        self.base_url = getattr(
            settings,
            "GOOGLE_WEATHER_BASE_URL",
            "https://weather.googleapis.com/v1/forecast/days:lookup",
        )
        # Geocoding piggybacks on the Google Places key (already used by
        # LocalCostProvider). GeoNames is intentionally not used here: its free
        # webservice account must be separately enabled and silently 401s.
        self.places_url = getattr(
            settings,
            "GOOGLE_PLACES_TEXT_SEARCH_URL",
            "https://places.googleapis.com/v1/places:searchText",
        ).rstrip("/")
        self.places_api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "") or getattr(
            settings,
            "GOOGLE_MAPS_API_KEY",
            "",
        )

    def _geocode(self, city: str, country: str) -> tuple[float, float]:
        if not self.places_api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY is required for weather geocoding.")
        data = _http_request_json(
            "POST",
            self.places_url,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.places_api_key,
                "X-Goog-FieldMask": "places.location",
            },
            payload={"textQuery": f"{city}, {country}", "maxResultCount": 1},
        )
        places = data.get("places", [])
        if not places:
            raise ValueError(f"Cannot geocode '{city}, {country}'.")
        location = places[0].get("location", {})
        lat, lng = location.get("latitude"), location.get("longitude")
        if lat is None or lng is None:
            raise ValueError(f"Cannot geocode '{city}, {country}'.")
        return float(lat), float(lng)

    def fetch_summary(
        self,
        destination_city: str,
        destination_country: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("GOOGLE_WEATHER_API_KEY is missing.")

        lat, lng = self._geocode(destination_city, destination_country)

        today = date.today()
        trip_start = _parse_date(start_date) if start_date else None
        trip_end = _parse_date(end_date) if end_date else None

        days_until_trip = (trip_start - today).days if trip_start else 0
        within_forecast = bool(trip_start and 0 <= days_until_trip < 10)

        try:
            data = _http_request_json(
                "GET",
                self.base_url,
                params={
                    "location.latitude": lat,
                    "location.longitude": lng,
                    "days": 10,
                    "key": self.api_key,
                },
            )
        except HTTPError as exc:
            # Google Weather has regional coverage gaps (e.g. Japan) and returns
            # 404 NOT_FOUND for unsupported locations. Surface that as a clear,
            # user-facing message instead of a generic 503.
            if exc.code == 404:
                raise ValueError(
                    f"Weather data isn't available for "
                    f"{destination_city}, {destination_country} yet."
                )
            raise

        all_days = data.get("forecastDays", [])
        if not all_days:
            raise ValueError("Google Weather API returned no forecast data.")

        # Use only the days that fall within the trip window when in range.
        days_to_parse = all_days
        if within_forecast and trip_start and trip_end:
            filtered = [
                d for d in all_days
                if self._day_in_range(d.get("displayDate", {}), trip_start, trip_end)
            ]
            if filtered:
                days_to_parse = filtered

        if trip_start and trip_end:
            if within_forecast:
                date_label = (
                    f"Forecast for your trip"
                    f" ({trip_start.strftime('%b %d')} – {trip_end.strftime('%b %d')})"
                )
            else:
                date_label = (
                    f"Current conditions"
                    f" (seasonal reference for {trip_start.strftime('%B')})"
                )
        else:
            date_label = "Current 10-day forecast"

        result = self._parse({"forecastDays": days_to_parse})
        result["date_label"] = date_label
        result["is_forecast"] = within_forecast
        return result

    @staticmethod
    def _day_in_range(d: Dict[str, Any], start: date, end: date) -> bool:
        try:
            return start <= date(d["year"], d["month"], d["day"]) <= end
        except (KeyError, TypeError, ValueError):
            return False

    @staticmethod
    def _parse(data: Dict[str, Any]) -> Dict[str, Any]:
        days = data.get("forecastDays", [])
        if not days:
            raise ValueError("Google Weather API returned no forecast data.")

        max_temps: List[float] = []
        min_temps: List[float] = []
        humidities: List[int] = []
        precip_probs: List[int] = []
        conditions: List[str] = []

        for day in days:
            t_max = day.get("maxTemperature", {}).get("degrees")
            t_min = day.get("minTemperature", {}).get("degrees")
            if t_max is not None:
                max_temps.append(float(t_max))
            if t_min is not None:
                min_temps.append(float(t_min))

            day_fc = day.get("daytimeForecast", {})
            # relativeHumidity is a direct field on daytimeForecast in the
            # Google Weather API — not nested under a "humidity" sub-object.
            h = day_fc.get("relativeHumidity") or day_fc.get("humidity", {}).get("relativeHumidity")
            if h is not None:
                humidities.append(int(h))

            p = day_fc.get("precipitation", {}).get("probability", {}).get("percent")
            if p is not None:
                precip_probs.append(int(p))

            # Condition text may be on daytimeForecast or directly on the day.
            cond = (
                day_fc.get("weatherCondition", {}).get("description", {}).get("text")
                or day.get("daySummary")
            )
            if cond:
                conditions.append(cond)

        avg_high = round(sum(max_temps) / len(max_temps), 1) if max_temps else 0.0
        avg_low = round(sum(min_temps) / len(min_temps), 1) if min_temps else 0.0
        avg_humidity = round(sum(humidities) / len(humidities)) if humidities else 0
        avg_precip = round(sum(precip_probs) / len(precip_probs)) if precip_probs else 0
        condition = max(set(conditions), key=conditions.count) if conditions else "Varied"

        def to_f(c: float) -> float:
            return round(c * 9 / 5 + 32, 1)

        return {
            "condition": condition,
            "high_c": avg_high,
            "low_c": avg_low,
            "high_f": to_f(avg_high),
            "low_f": to_f(avg_low),
            "humidity_pct": avg_humidity,
            "precipitation_pct": avg_precip,
        }


# WMO weather codes → text containing the keywords the UI maps to icons
# (rain / cloud / sun / clear).
_WMO_CONDITIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Rain showers", 82: "Heavy rain showers",
    85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm with hail",
}


class OpenMeteoWeatherProvider:
    """Free, global, keyless weather — used as a fallback and for far-future trips.

    Near dates use the 16-day forecast; dates beyond that fall back to the same
    calendar window one year earlier (a realistic seasonal reference) via the
    historical archive — far better than reporting today's conditions.
    """

    GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

    def _geocode(self, city: str, country: str) -> tuple[float, float]:
        data = _http_request_json(
            "GET", self.GEOCODE_URL,
            params={"name": city, "count": 5, "language": "en", "format": "json"},
        )
        results = data.get("results") or []
        if not results:
            raise ValueError(f"Cannot geocode '{city}, {country}'.")
        # Prefer a result whose country matches, else take the top hit.
        target = (country or "").strip().lower()
        chosen = next(
            (r for r in results if (r.get("country") or "").lower() == target),
            results[0],
        )
        return float(chosen["latitude"]), float(chosen["longitude"])

    def fetch_summary(
        self,
        destination_city: str,
        destination_country: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Dict[str, Any]:
        lat, lng = self._geocode(destination_city, destination_country)
        today = date.today()
        trip_start = _parse_date(start_date) if start_date else today
        trip_end = _parse_date(end_date) if end_date else trip_start

        days_until = (trip_start - today).days
        within_forecast = 0 <= days_until <= 14 and (trip_end - today).days <= 15

        daily = "temperature_2m_max,temperature_2m_min,weathercode,precipitation_probability_max"
        if within_forecast:
            params = {
                "latitude": lat, "longitude": lng, "daily": daily,
                "hourly": "relative_humidity_2m", "timezone": "auto",
                "start_date": trip_start.isoformat(), "end_date": trip_end.isoformat(),
            }
            url = self.FORECAST_URL
            is_forecast = True
            label = (f"Forecast for your trip "
                     f"({trip_start.strftime('%b %d')} – {trip_end.strftime('%b %d')})")
        else:
            # Same window, one year ago — a seasonal reference from the archive.
            ref_start = trip_start.replace(year=trip_start.year - 1)
            ref_end = trip_end.replace(year=trip_end.year - 1)
            params = {
                "latitude": lat, "longitude": lng,
                "daily": "temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum",
                "hourly": "relative_humidity_2m", "timezone": "auto",
                "start_date": ref_start.isoformat(), "end_date": ref_end.isoformat(),
            }
            url = self.ARCHIVE_URL
            is_forecast = False
            label = (f"Seasonal reference for {trip_start.strftime('%B')} "
                     f"(historical {ref_start.year})")

        data = _http_request_json("GET", url, params=params)
        result = self._parse(data)
        result["date_label"] = label
        result["is_forecast"] = is_forecast
        return result

    @staticmethod
    def _parse(data: Dict[str, Any]) -> Dict[str, Any]:
        daily = data.get("daily") or {}
        highs = [t for t in (daily.get("temperature_2m_max") or []) if t is not None]
        lows = [t for t in (daily.get("temperature_2m_min") or []) if t is not None]
        codes = [c for c in (daily.get("weathercode") or []) if c is not None]
        if not highs or not lows:
            raise ValueError("Open-Meteo returned no temperature data.")

        hourly = data.get("hourly") or {}
        humidities = [h for h in (hourly.get("relative_humidity_2m") or []) if h is not None]

        # Precipitation chance: probability when forecasting, else share of wet days.
        probs = [p for p in (daily.get("precipitation_probability_max") or []) if p is not None]
        if probs:
            precip_pct = round(sum(probs) / len(probs))
        else:
            sums = [s for s in (daily.get("precipitation_sum") or []) if s is not None]
            precip_pct = round(100 * sum(1 for s in sums if s > 0.1) / len(sums)) if sums else 0

        avg_high = round(sum(highs) / len(highs), 1)
        avg_low = round(sum(lows) / len(lows), 1)
        avg_humidity = round(sum(humidities) / len(humidities)) if humidities else 0
        condition = (
            _WMO_CONDITIONS.get(max(set(codes), key=codes.count), "Varied")
            if codes else "Varied"
        )

        def to_f(c: float) -> float:
            return round(c * 9 / 5 + 32, 1)

        return {
            "condition": condition,
            "high_c": avg_high, "low_c": avg_low,
            "high_f": to_f(avg_high), "low_f": to_f(avg_low),
            "humidity_pct": avg_humidity, "precipitation_pct": precip_pct,
        }


def fetch_destination_weather(
    destination_city: str,
    destination_country: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict[str, Any]:
    """Weather summary for a destination.

    Google Weather only forecasts ~10 days, so for trips further out (the common
    case) and for regions Google doesn't cover, we use Open-Meteo — which also
    provides a realistic seasonal reference from history for far-future dates.
    """
    today = date.today()
    trip_start = _parse_date(start_date) if start_date else None
    near = bool(trip_start and 0 <= (trip_start - today).days <= 9)

    # For near trips Google's live forecast is best; otherwise prefer Open-Meteo's
    # seasonal reference. Whichever is primary, the other is the fallback.
    primary, fallback = (
        (GoogleWeatherProvider, OpenMeteoWeatherProvider) if near
        else (OpenMeteoWeatherProvider, GoogleWeatherProvider)
    )
    try:
        return primary().fetch_summary(
            destination_city, destination_country, start_date, end_date
        )
    except Exception:
        return fallback().fetch_summary(
            destination_city, destination_country, start_date, end_date
        )


def _normalize_duration_days(departure_date: str, return_date: str) -> int:
    departure = _parse_date(departure_date)
    returning = _parse_date(return_date)
    days = (returning - departure).days
    if days <= 0:
        raise ValueError("return_date must be after departure_date.")
    return days


# Daily local-living estimate (food, transport, incidentals) derived from the
# nightly lodging price of each tier. LiteAPI does not return cost-of-living
# data, so we infer it from the real, fetched hotel prices: pricier tiers imply
# pricier daily spending, bounded by sensible floors/caps so a single luxury
# hotel rate can't produce absurd food costs.
_LIVING_FACTOR = {
    "cheapest": Decimal("0.35"),
    "affordable": Decimal("0.45"),
    "moderate": Decimal("0.55"),
    "luxury": Decimal("0.70"),
}
_LIVING_FLOOR = {
    "cheapest": Decimal("18"),
    "affordable": Decimal("30"),
    "moderate": Decimal("50"),
    "luxury": Decimal("85"),
}
_LIVING_CAP = {
    "cheapest": Decimal("70"),
    "affordable": Decimal("120"),
    "moderate": Decimal("200"),
    "luxury": Decimal("380"),
}


def _living_daily_cost(tier: str, hotel_daily: Decimal) -> Decimal:
    value = hotel_daily * _LIVING_FACTOR[tier]
    return min(max(value, _LIVING_FLOOR[tier]), _LIVING_CAP[tier])


def _representative_tier_prices(
    tiers: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Decimal | None]:
    """Cheapest option price in each tier, with empty tiers filled from the
    nearest populated neighbour so the four categories stay monotonic."""
    raw: Dict[str, Decimal | None] = {}
    for tier in TIER_ORDER:
        prices = [
            _safe_decimal(option.get("price"))
            for option in (tiers.get(tier) or [])
        ]
        prices = [p for p in prices if p and p > 0]
        raw[tier] = min(prices) if prices else None

    # Forward then backward fill so leading/trailing gaps borrow a real price.
    last: Decimal | None = None
    for tier in TIER_ORDER:
        if raw[tier] is None:
            raw[tier] = last
        else:
            last = raw[tier]
    last = None
    for tier in reversed(TIER_ORDER):
        if raw[tier] is None:
            raw[tier] = last
        else:
            last = raw[tier]
    return raw


def build_dynamic_tier_quotes(input_data: DynamicPricingInput) -> DynamicTierQuoteResult:
    if input_data.adults <= 0:
        raise ValueError("adults must be greater than zero.")

    trip_duration_days = _normalize_duration_days(
        input_data.departure_date,
        input_data.return_date,
    )

    flight_input = FlightSearchInput(
        origin_city=input_data.origin_city,
        destination_city=input_data.destination_city,
        departure_date=input_data.departure_date,
        return_date=input_data.return_date,
        adults=input_data.adults,
        currency=input_data.currency,
    )
    hotel_input = HotelSearchInput(
        destination_city=input_data.destination_city,
        destination_country=input_data.destination_country,
        check_in=input_data.departure_date,
        check_out=input_data.return_date,
        adults=input_data.adults,
        currency=input_data.currency,
    )

    # Flights and hotels are independent network calls — run them concurrently
    # (urllib releases the GIL during I/O) to roughly halve dashboard load time.
    with ThreadPoolExecutor(max_workers=2) as executor:
        flight_future = executor.submit(
            lambda: NuiteeFlightProvider().search_options(flight_input)
        )
        hotel_future = executor.submit(
            lambda: NuiteeHotelProvider().search_options(hotel_input)
        )
        flight_result = flight_future.result()
        hotel_result = hotel_future.result()

    flight_prices = _representative_tier_prices(flight_result["tiers"])
    hotel_totals = _representative_tier_prices(hotel_result["tiers"])

    if all(v is None for v in flight_prices.values()):
        raise ValueError("No flight pricing could be derived for this route.")
    if all(v is None for v in hotel_totals.values()):
        raise ValueError("No hotel pricing could be derived for this destination.")

    tiers: Dict[str, TierCostBreakdown] = {}
    duration_decimal = Decimal(trip_duration_days)
    for tier in TIER_ORDER:
        flight_cost = flight_prices[tier] or Decimal("0")
        hotel_total = hotel_totals[tier] or Decimal("0")
        # Hotel option price is the total for the stay — convert to a nightly rate.
        hotel_daily = (hotel_total / duration_decimal) if duration_decimal else hotel_total
        local_daily = _living_daily_cost(tier, hotel_daily)
        total_daily_living = hotel_daily + local_daily
        total_living_cost = total_daily_living * duration_decimal
        total_trip_cost = flight_cost + total_living_cost

        tiers[tier] = {
            "flight_cost": float(flight_cost),
            "hotel_daily_cost": float(hotel_daily),
            "local_daily_cost": float(local_daily),
            "total_daily_living_cost": float(total_daily_living),
            "total_living_cost": float(total_living_cost),
            "total_trip_cost": float(total_trip_cost),
        }

    return {
        "destination_city": input_data.destination_city,
        "destination_country": input_data.destination_country,
        "trip_duration_days": trip_duration_days,
        "currency": input_data.currency,
        "tiers": tiers,
        "sources": {
            "flights": "nuitee_liteapi_flights",
            "hotels": "nuitee_liteapi_hotels",
            "local_costs": "derived_from_lodging",
        },
    }


def evaluate_dynamic_budget(input_data: DynamicPricingInput) -> BudgetEvaluationResult:
    comfort = input_data.comfort_preference.strip().lower()
    if comfort not in VALID_COMFORT_TIERS:
        raise ValueError(f"Unsupported comfort_preference: {input_data.comfort_preference}")
    if input_data.total_living_budget < 0:
        raise ValueError("total_living_budget cannot be negative.")
    if input_data.max_flight_budget < 0:
        raise ValueError("max_flight_budget cannot be negative.")

    snapshot = build_dynamic_tier_quotes(input_data)
    tier = snapshot["tiers"][comfort]
    duration = Decimal(snapshot["trip_duration_days"])

    selected_tier_daily_cost = Decimal(str(tier["total_daily_living_cost"]))
    actual_daily_allowance = input_data.total_living_budget / duration
    total_expected_ground_cost = Decimal(str(tier["total_living_cost"]))

    feasible = actual_daily_allowance >= selected_tier_daily_cost
    if feasible:
        total_shortfall = Decimal("0")
        optimized_duration_days = None
        warning = None
        message = None
    else:
        daily_shortfall = selected_tier_daily_cost - actual_daily_allowance
        total_shortfall = daily_shortfall * duration
        optimized_duration_days = int(
            (input_data.total_living_budget / selected_tier_daily_cost).to_integral_value(
                rounding=ROUND_FLOOR
            )
        )
        warning = (
            "Selected category is not feasible for current living budget and duration."
        )
        message = (
            "Reduce duration or switch to a lower category after reviewing dynamic quotes."
        )

    return {
        "feasible": feasible,
        "metrics": {
            "selected_tier_daily_cost": float(selected_tier_daily_cost),
            "actual_daily_allowance": float(actual_daily_allowance),
            "total_expected_ground_cost": float(total_expected_ground_cost),
            "total_shortfall": float(total_shortfall),
        },
        "warnings": warning,
        "suggestions": {
            "optimized_duration_days": optimized_duration_days,
            "message": message,
        },
        "pricing_snapshot": snapshot,
    }


# ---------------------------------------------------------------------------
# LiteAPI (Nuitee Connect) — individual flight & hotel options for selection
#
# Unlike build_dynamic_tier_quotes (which returns aggregate per-tier averages),
# these providers return *individual, selectable* flight and hotel options,
# grouped into the same four comfort tiers, 2-3 options per tier.
# ---------------------------------------------------------------------------


class FlightOption(TypedDict):
    id: str
    airline: str
    price: float
    currency: str
    stops: int
    duration_minutes: int
    departure_time: str
    arrival_time: str
    origin: str
    destination: str
    provider: str


class HotelOption(TypedDict):
    id: str
    name: str
    price: float
    currency: str
    nights: int
    stars: int
    rating: float
    board_name: str
    refundable: bool
    thumbnail: str
    address: str


class CategorizedFlightResult(TypedDict):
    origin: str
    destination: str
    currency: str
    tiers: Dict[str, List[FlightOption]]


class CategorizedHotelResult(TypedDict):
    destination_city: str
    destination_country: str
    currency: str
    nights: int
    tiers: Dict[str, List[HotelOption]]


@dataclass(frozen=True)
class FlightSearchInput:
    origin_city: str
    destination_city: str
    departure_date: str
    return_date: str
    adults: int
    currency: str = "USD"


@dataclass(frozen=True)
class HotelSearchInput:
    destination_city: str
    destination_country: str
    check_in: str
    check_out: str
    adults: int
    currency: str = "USD"


def _bucket_options_by_price(
    options: List[Dict[str, Any]],
    price_key: str = "price",
    per_tier: int = 3,
) -> Dict[str, List[Dict[str, Any]]]:
    """Split priced options into the four comfort tiers by price quantile.

    The cheapest options land in 'cheapest' and the most expensive in 'luxury'.
    Each tier holds up to `per_tier` options (the cheapest representatives of
    that price band). Degrades gracefully: with fewer options than tiers, some
    tiers stay empty rather than raising.
    """
    ordered = sorted(
        (
            o
            for o in options
            if (_safe_decimal(o.get(price_key)) or Decimal("0")) > 0
        ),
        key=lambda o: _safe_decimal(o.get(price_key)),
    )
    buckets: Dict[str, List[Dict[str, Any]]] = {tier: [] for tier in TIER_ORDER}
    total = len(ordered)
    if total == 0:
        return buckets

    bands = len(TIER_ORDER)
    for index, option in enumerate(ordered):
        band = min((index * bands) // total, bands - 1)
        buckets[TIER_ORDER[band]].append(option)

    return {tier: buckets[tier][:per_tier] for tier in TIER_ORDER}


class LiteApiClient:
    """Facade over LiteAPI (Nuitee Connect) HTTP calls.

    Mirrors SerpApiClient: hides URL building, API-key header injection, and
    response parsing. All requests flow through _http_request_json so they are
    logged (and the key redacted) by the Observer logging layer automatically.
    """

    def __init__(self):
        self.base_url = settings.NUITEE_BASE_URL.rstrip("/")
        self.api_key = settings.NUITEE_API_KEY

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("NUITEE_API_KEY is missing.")
        return {"X-API-Key": self.api_key, "accept": "application/json"}

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return _http_request_json(
            method="POST",
            url=f"{self.base_url}/{path.lstrip('/')}",
            headers=self._headers(),
            payload=payload,
        )

    def get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return _http_request_json(
            method="GET",
            url=f"{self.base_url}/{path.lstrip('/')}",
            headers=self._headers(),
            params=params,
        )


class NuiteeFlightProvider:
    def __init__(self):
        self.client = LiteApiClient()

    def _resolve_airport(self, city_or_code: str) -> str:
        code = _coerce_iata_code(city_or_code)
        if code:
            return code

        query = city_or_code.split(",")[0].strip()
        try:
            response = self.client.get("data/flights/airports", {"q": query})
        except Exception as exc:
            raise ValueError(
                f"Unable to resolve an airport for '{city_or_code}'."
            ) from exc

        # Prefer the metro "All Airports" code (aggregates every airport in the
        # city, so it returns the widest set of flights), then any serviceable
        # airport, then anything valid. priority 0 < 1 < 2.
        candidates: List[tuple[int, str]] = []
        for group in response.get("data") or []:
            for airport in group.get("airports", []):
                iata = (airport.get("iata") or "").strip().upper()
                if len(iata) != 3 or not iata.isalpha():
                    continue
                name = (airport.get("name") or "").lower()
                if "all airport" in name:
                    priority = 0
                elif airport.get("hasAirlineService"):
                    priority = 1
                else:
                    priority = 2
                candidates.append((priority, iata))

        if not candidates:
            raise ValueError(f"Unable to resolve an airport for '{city_or_code}'.")
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    @staticmethod
    def _journey_to_option(journey: Dict[str, Any]) -> FlightOption | None:
        offer = journey.get("cheapestOffer") or {}
        pricing = (offer.get("pricing") or {}).get("display") or {}
        price = _safe_decimal(pricing.get("total"))
        if price is None or price <= 0:
            return None

        segments = journey.get("segments") or []
        outbound = [s for s in segments if s.get("direction") == "OUTBOUND"] or segments
        first = outbound[0] if outbound else {}
        last = outbound[-1] if outbound else {}
        carrier = first.get("carrier") or {}
        provider = offer.get("provider") or {}
        airline = (
            carrier.get("marketingName")
            or carrier.get("operatingName")
            or provider.get("code")
            or "Unknown carrier"
        )
        duration = (journey.get("totalDuration") or {}).get("minutes") or 0

        return {
            "id": offer.get("offerId") or journey.get("journeyKey") or "",
            "airline": airline,
            "price": float(price),
            "currency": pricing.get("currency") or "USD",
            "stops": max(len(outbound) - 1, 0),
            "duration_minutes": int(duration),
            "departure_time": first.get("departureTime") or "",
            "arrival_time": last.get("arrivalTime") or "",
            "origin": first.get("originCode") or "",
            "destination": last.get("destinationCode") or "",
            "provider": provider.get("code") or "nuitee",
        }

    def search_options(self, input_data: FlightSearchInput) -> CategorizedFlightResult:
        origin_code = self._resolve_airport(input_data.origin_city)
        destination_code = self._resolve_airport(input_data.destination_city)

        legs = [
            {
                "origin": origin_code,
                "destination": destination_code,
                "date": input_data.departure_date,
            }
        ]
        if input_data.return_date:
            legs.append(
                {
                    "origin": destination_code,
                    "destination": origin_code,
                    "date": input_data.return_date,
                }
            )

        response = self.client.post(
            "flights/rates",
            {
                "legs": legs,
                "adults": input_data.adults,
                "currency": input_data.currency,
            },
        )

        data = response.get("data") or []
        journeys = data[0].get("journeys", []) if data else []

        options: List[Dict[str, Any]] = []
        seen: set[tuple] = set()
        for journey in journeys:
            option = self._journey_to_option(journey)
            if not option:
                continue
            # Collapse identical itineraries (same carrier, price, times, stops)
            # so each tier shows genuinely distinct flights.
            signature = (
                option["airline"],
                option["price"],
                option["departure_time"],
                option["arrival_time"],
                option["stops"],
            )
            if signature in seen:
                continue
            seen.add(signature)
            options.append(option)

        if not options:
            raise ValueError(
                "No flight options were returned for this route and dates."
            )

        return {
            "origin": origin_code,
            "destination": destination_code,
            "currency": input_data.currency,
            "tiers": _bucket_options_by_price(options),
        }


class NuiteeHotelProvider:
    def __init__(self):
        self.client = LiteApiClient()

    def _hotel_directory(self, hotel_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Resolve hotel ids to display metadata (name, stars, photo, address)."""
        if not hotel_ids:
            return {}
        try:
            response = self.client.get(
                "data/hotels", {"hotelIds": ",".join(hotel_ids)}
            )
        except Exception:
            # Names are a nicety; never fail the search over them.
            return {}
        directory: Dict[str, Dict[str, Any]] = {}
        for hotel in response.get("data") or []:
            hotel_id = hotel.get("id")
            if hotel_id:
                directory[hotel_id] = hotel
        return directory

    @staticmethod
    def _cheapest_offer(hotel: Dict[str, Any]) -> tuple[Decimal, Dict[str, Any]] | None:
        """Return (price, room-type) for the cheapest offer of a hotel."""
        best: tuple[Decimal, Dict[str, Any]] | None = None
        for room_type in hotel.get("roomTypes") or []:
            offer_rate = room_type.get("offerRetailRate") or {}
            price = _safe_decimal(offer_rate.get("amount"))
            if price is None or price <= 0:
                # Fall back to the first rate's retail total.
                rates = room_type.get("rates") or []
                if rates:
                    total = (rates[0].get("retailRate") or {}).get("total") or []
                    if total:
                        price = _safe_decimal(total[0].get("amount"))
            if price is not None and price > 0:
                if best is None or price < best[0]:
                    best = (price, room_type)
        return best

    def search_options(self, input_data: HotelSearchInput) -> CategorizedHotelResult:
        nights = max(
            _normalize_duration_days(input_data.check_in, input_data.check_out), 1
        )
        response = self.client.post(
            "hotels/rates",
            {
                "aiSearch": f"{input_data.destination_city}, {input_data.destination_country}",
                "checkin": input_data.check_in,
                "checkout": input_data.check_out,
                "occupancies": [{"adults": input_data.adults}],
                "currency": input_data.currency,
                "guestNationality": "US",
                "limit": 30,
            },
        )

        hotels = response.get("data") or []
        priced: List[tuple[str, Decimal, Dict[str, Any]]] = []
        for hotel in hotels:
            hotel_id = hotel.get("hotelId") or ""
            cheapest = self._cheapest_offer(hotel)
            if cheapest is None:
                continue
            price, room_type = cheapest
            priced.append((hotel_id, price, room_type))

        if not priced:
            raise ValueError(
                "No hotel options were returned for this destination and dates."
            )

        directory = self._hotel_directory([hid for hid, _, _ in priced if hid])

        options: List[Dict[str, Any]] = []
        for hotel_id, price, room_type in priced:
            meta = directory.get(hotel_id, {})
            rates = room_type.get("rates") or []
            first_rate = rates[0] if rates else {}
            cancellation = first_rate.get("cancellationPolicies") or {}
            refundable_tag = (cancellation.get("refundableTag") or "").upper()
            offer_rate = room_type.get("offerRetailRate") or {}

            options.append(
                {
                    "id": room_type.get("offerId") or hotel_id,
                    "name": meta.get("name") or f"Hotel {hotel_id}",
                    "price": float(price),
                    "currency": offer_rate.get("currency") or input_data.currency,
                    "nights": nights,
                    "stars": int(meta.get("stars") or 0),
                    "rating": float(meta.get("rating") or 0),
                    "board_name": first_rate.get("boardName") or "Room Only",
                    "refundable": refundable_tag == "RFN",
                    "thumbnail": meta.get("main_photo") or "",
                    "address": meta.get("address") or "",
                }
            )

        return {
            "destination_city": input_data.destination_city,
            "destination_country": input_data.destination_country,
            "currency": input_data.currency,
            "nights": nights,
            "tiers": _bucket_options_by_price(options),
        }


def search_flight_options(input_data: FlightSearchInput) -> CategorizedFlightResult:
    if input_data.adults <= 0:
        raise ValueError("adults must be greater than zero.")
    return NuiteeFlightProvider().search_options(input_data)


def search_hotel_options(input_data: HotelSearchInput) -> CategorizedHotelResult:
    if input_data.adults <= 0:
        raise ValueError("adults must be greater than zero.")
    return NuiteeHotelProvider().search_options(input_data)


# ---------------------------------------------------------------------------
# Booking — real LiteAPI (Nuitee) sandbox hotel booking
#
# The checkout "Pay" action calls this. It performs the real two-step LiteAPI
# flow (prebook → book) against the sandbox using the WALLET payment method
# (sandbox credit), producing a genuine booking that appears in the Nuitee
# Connect dashboard. No real money moves — the sandbox key is test-only.
# ---------------------------------------------------------------------------


class BookingConfirmation(TypedDict):
    booking_id: str
    supplier_booking_id: str | None
    status: str
    hotel_confirmation_code: str | None
    price: float | None
    currency: str | None


@dataclass(frozen=True)
class HotelBookingInput:
    offer_id: str
    first_name: str
    last_name: str
    email: str


class NuiteeBookingProvider:
    def __init__(self):
        self.client = LiteApiClient()

    def book_hotel(self, input_data: HotelBookingInput) -> BookingConfirmation:
        prebook = self.client.post(
            "rates/prebook",
            {"offerId": input_data.offer_id, "usePaymentSdk": False},
        )
        prebook_data = prebook.get("data") or {}
        prebook_id = prebook_data.get("prebookId")
        if not prebook_id:
            raise ValueError(
                "This rate is no longer available to book — please re-run the "
                "search and select the hotel again."
            )

        holder = {
            "firstName": input_data.first_name,
            "lastName": input_data.last_name,
            "email": input_data.email,
        }
        booking = self.client.post(
            "rates/book",
            {
                "prebookId": prebook_id,
                "holder": holder,
                "guests": [
                    {
                        "occupancyNumber": 1,
                        "firstName": input_data.first_name,
                        "lastName": input_data.last_name,
                        "email": input_data.email,
                        "remarks": "",
                    }
                ],
                # Sandbox payment via test wallet credit — no card is charged.
                "payment": {"method": "WALLET"},
            },
        )
        data = booking.get("data") or {}
        booking_id = data.get("bookingId")
        if not booking_id:
            raise ValueError("The supplier did not confirm this booking.")

        return {
            "booking_id": booking_id,
            "supplier_booking_id": data.get("supplierBookingId"),
            "status": data.get("status") or "CONFIRMED",
            "hotel_confirmation_code": data.get("hotelConfirmationCode"),
            "price": float(_safe_decimal(prebook_data.get("price")) or 0)
            if prebook_data.get("price") is not None
            else None,
            "currency": prebook_data.get("currency"),
        }


def create_hotel_booking(input_data: HotelBookingInput) -> BookingConfirmation:
    if not input_data.offer_id:
        raise ValueError("A hotel offer is required to book.")
    return NuiteeBookingProvider().book_hotel(input_data)


@dataclass(frozen=True)
class FlightBookingInput:
    offer_id: str
    first_name: str
    last_name: str
    email: str
    airline: str = ""
    price: float | None = None
    currency: str = "USD"


def _make_booking_reference(prefix: str = "VTG") -> str:
    import secrets
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return f"{prefix}-" + "".join(secrets.choice(alphabet) for _ in range(6))


def create_flight_booking(input_data: FlightBookingInput) -> BookingConfirmation:
    """Issue a demo flight confirmation.

    LiteAPI's sandbox does not support holding/booking flight offers (they expire
    within minutes), so this records a demo confirmation rather than a live
    supplier booking. It is intentionally deterministic and side-effect free.
    """
    if not input_data.offer_id:
        raise ValueError("A flight offer is required to book.")
    return {
        "booking_id": _make_booking_reference(),
        "supplier_booking_id": None,
        "status": "CONFIRMED",
        "hotel_confirmation_code": None,
        "price": float(input_data.price) if input_data.price is not None else None,
        "currency": input_data.currency or "USD",
    }

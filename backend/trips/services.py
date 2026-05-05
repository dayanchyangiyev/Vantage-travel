from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
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


class SerpApiClient:
    def __init__(self):
        self.base_url = settings.SERPAPI_BASE_URL.rstrip("/")
        self.api_key = settings.SERPAPI_API_KEY

    def search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY is missing.")
        merged = dict(params)
        merged["api_key"] = self.api_key
        return _http_request_json(
            method="GET",
            url=self.base_url,
            params=merged,
        )


def _extract_iata_codes(node: Any) -> List[str]:
    found: List[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            key_lower = key.lower()
            if key_lower in {"id", "airport_code", "iata", "iata_code"} and isinstance(value, str):
                code = value.strip().upper()
                if len(code) == 3 and code.isalpha():
                    found.append(code)
            found.extend(_extract_iata_codes(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_extract_iata_codes(item))
    return found


class SerpApiFlightProvider:
    def __init__(self):
        self.client = SerpApiClient()

    def _resolve_location_to_airport(self, city_or_code: str) -> str:
        iata = _coerce_iata_code(city_or_code)
        if iata:
            return iata

        response = self.client.search(
            {
                "engine": "google_flights_autocomplete",
                "q": city_or_code,
                "hl": "en",
                "gl": "us",
            }
        )
        codes = _extract_iata_codes(response)
        if not codes:
            raise ValueError(f"Unable to resolve location to airport code: {city_or_code}")
        return codes[0]

    def fetch_prices(
        self,
        origin_city: str,
        destination_city: str,
        departure_date: str,
        return_date: str,
        adults: int,
        currency: str,
    ) -> List[Decimal]:
        origin_code = self._resolve_location_to_airport(origin_city)
        destination_code = self._resolve_location_to_airport(destination_city)

        response = self.client.search(
            {
                "engine": "google_flights",
                "departure_id": origin_code,
                "arrival_id": destination_code,
                "outbound_date": departure_date,
                "return_date": return_date,
                "adults": adults,
                "currency": currency,
                "hl": "en",
                "gl": "us",
            }
        )

        prices: List[Decimal] = []
        for key in ("best_flights", "other_flights"):
            for offer in response.get(key, []):
                price = _safe_decimal(offer.get("price"))
                if price and price > 0:
                    prices.append(price)

        if not prices:
            fallback = [p for p in _extract_numeric_candidates(response) if p > 0]
            if not fallback:
                raise ValueError("SerpAPI flights returned no usable flight prices.")
            return fallback
        return prices

    @staticmethod
    def _extract_prices(response: Dict[str, Any]) -> List[Decimal]:
        prices: List[Decimal] = []
        for key in ("best_flights", "other_flights"):
            for offer in response.get(key, []):
                price = _safe_decimal(offer.get("price"))
                if price and price > 0:
                    prices.append(price)
        if prices:
            return prices
        return [p for p in _extract_numeric_candidates(response) if p > 0]

    def _search_prices(self, params: Dict[str, Any]) -> List[Decimal]:
        response = self.client.search(params)
        return self._extract_prices(response)

    def fetch_tier_prices(
        self,
        origin_city: str,
        destination_city: str,
        departure_date: str,
        return_date: str,
        adults: int,
        currency: str,
    ) -> Dict[str, Decimal]:
        origin_code = self._resolve_location_to_airport(origin_city)
        destination_code = self._resolve_location_to_airport(destination_city)
        base = {
            "engine": "google_flights",
            "departure_id": origin_code,
            "arrival_id": destination_code,
            "outbound_date": departure_date,
            "return_date": return_date,
            "adults": adults,
            "currency": currency,
            "hl": "en",
            "gl": "us",
            "sort_by": 2,  # price sort for stable tier buckets
            "show_hidden": True,
        }

        # Segmented datasets by travel class to avoid collapsing all tiers
        # into a single economy-like market slice.
        tier_query_sets: Dict[str, List[Dict[str, Any]]] = {
            "cheapest": [{"travel_class": 1, "stops": 0}],
            "affordable": [{"travel_class": 1, "stops": 2}, {"travel_class": 2, "stops": 0}],
            "moderate": [{"travel_class": 2, "stops": 0}],
            "luxury": [{"travel_class": 3, "stops": 0}, {"travel_class": 4, "stops": 0}],
        }

        tier_buckets: Dict[str, List[Decimal]] = {tier: [] for tier in TIER_ORDER}
        global_pool: List[Decimal] = []
        for tier in TIER_ORDER:
            for query_patch in tier_query_sets[tier]:
                try:
                    prices = self._search_prices({**base, **query_patch})
                except Exception:
                    continue
                valid_prices = [p for p in prices if p > 0]
                if valid_prices:
                    tier_buckets[tier].extend(valid_prices)
                    global_pool.extend(valid_prices)

        if not global_pool:
            raise ValueError("SerpAPI flights returned no usable segmented prices.")

        tiers: Dict[str, Decimal] = {}
        for tier in TIER_ORDER:
            source = sorted(tier_buckets[tier]) if tier_buckets[tier] else sorted(global_pool)
            tiers[tier] = _tier_value_from_sorted(source, TIER_PERCENTILES[tier])

        # Ensure non-decreasing tier ordering even when sparse data appears.
        last = Decimal("0")
        for tier in TIER_ORDER:
            if tiers[tier] < last:
                tiers[tier] = last
            last = tiers[tier]
        return tiers


class SerpApiHotelProvider:
    def __init__(self):
        self.client = SerpApiClient()

    def fetch_prices(
        self,
        destination_city: str,
        destination_country: str,
        check_in: str,
        check_out: str,
        adults: int,
        currency: str,
        trip_duration_days: int,
    ) -> List[Decimal]:
        query = f"{destination_city}, {destination_country}"
        offers_response = self.client.search(
            {
                "engine": "google_hotels",
                "q": query,
                "check_in_date": check_in,
                "check_out_date": check_out,
                "adults": adults,
                "currency": currency,
                "hl": "en",
                "gl": "us",
                "sort_by": 3,  # lowest price first
            }
        )

        daily_prices: List[Decimal] = []
        for property_item in offers_response.get("properties", []):
            amount = (
                _safe_decimal(
                    property_item.get("rate_per_night", {}).get("extracted_lowest")
                )
                or _safe_decimal(
                    property_item.get("rate_per_night", {}).get("extracted_before_taxes_fees")
                )
                or _safe_decimal(property_item.get("extracted_price"))
                or _safe_decimal(property_item.get("price"))
            )
            if amount and amount > 0:
                daily_prices.append(amount)

        for ad_item in offers_response.get("ads", []):
            amount = _safe_decimal(ad_item.get("extracted_price") or ad_item.get("price"))
            if amount and amount > 0:
                daily_prices.append(amount)

        filtered = [p for p in daily_prices if p > 0]
        if not filtered:
            fallback = [
                p for p in _extract_numeric_candidates(offers_response) if p > 0
            ]
            if not fallback:
                raise ValueError("SerpAPI hotels returned no usable hotel prices.")
            return fallback
        return filtered

    @staticmethod
    def _extract_prices(response: Dict[str, Any]) -> List[Decimal]:
        daily_prices: List[Decimal] = []
        for property_item in response.get("properties", []):
            amount = (
                _safe_decimal(
                    property_item.get("rate_per_night", {}).get("extracted_lowest")
                )
                or _safe_decimal(
                    property_item.get("rate_per_night", {}).get("extracted_before_taxes_fees")
                )
                or _safe_decimal(property_item.get("extracted_price"))
                or _safe_decimal(property_item.get("price"))
            )
            if amount and amount > 0:
                daily_prices.append(amount)

        for ad_item in response.get("ads", []):
            amount = _safe_decimal(ad_item.get("extracted_price") or ad_item.get("price"))
            if amount and amount > 0:
                daily_prices.append(amount)

        if daily_prices:
            return daily_prices
        return [p for p in _extract_numeric_candidates(response) if p > 0]

    def _search_prices(self, params: Dict[str, Any]) -> List[Decimal]:
        response = self.client.search(params)
        return self._extract_prices(response)

    def fetch_tier_prices(
        self,
        destination_city: str,
        destination_country: str,
        check_in: str,
        check_out: str,
        adults: int,
        currency: str,
    ) -> Dict[str, Decimal]:
        query = f"{destination_city}, {destination_country}"
        base = {
            "engine": "google_hotels",
            "q": query,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "adults": adults,
            "currency": currency,
            "hl": "en",
            "gl": "us",
            "sort_by": 3,
        }

        # Segmented hotel subsets by hotel class/rating to produce materially
        # different distributions for each preference tier.
        tier_query_sets: Dict[str, List[Dict[str, Any]]] = {
            "cheapest": [{"hotel_class": "2,3", "sort_by": 3}],
            "affordable": [{"hotel_class": "3,4", "sort_by": 3}],
            "moderate": [{"hotel_class": "4", "rating": 8}],
            "luxury": [{"hotel_class": "5", "rating": 9}, {"hotel_class": "5", "sort_by": 8}],
        }

        tier_buckets: Dict[str, List[Decimal]] = {tier: [] for tier in TIER_ORDER}
        global_pool: List[Decimal] = []
        for tier in TIER_ORDER:
            for query_patch in tier_query_sets[tier]:
                try:
                    prices = self._search_prices({**base, **query_patch})
                except Exception:
                    continue
                valid_prices = [p for p in prices if p > 0]
                if valid_prices:
                    tier_buckets[tier].extend(valid_prices)
                    global_pool.extend(valid_prices)

        if not global_pool:
            raise ValueError("SerpAPI hotels returned no usable segmented prices.")

        tiers: Dict[str, Decimal] = {}
        for tier in TIER_ORDER:
            source = sorted(tier_buckets[tier]) if tier_buckets[tier] else sorted(global_pool)
            tiers[tier] = _tier_value_from_sorted(source, TIER_PERCENTILES[tier])

        last = Decimal("0")
        for tier in TIER_ORDER:
            if tiers[tier] < last:
                tiers[tier] = last
            last = tiers[tier]
        return tiers


class LocalCostProvider:
    def __init__(self):
        self.base_url = getattr(
            settings,
            "GOOGLE_PLACES_TEXT_SEARCH_URL",
            "https://places.googleapis.com/v1/places:searchText",
        ).rstrip("/")
        self.api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "") or getattr(
            settings,
            "GOOGLE_MAPS_API_KEY",
            "",
        )

    @staticmethod
    def _money_to_decimal(money: Dict[str, Any] | None) -> Decimal | None:
        if not isinstance(money, dict):
            return None
        units = _safe_decimal(money.get("units")) or Decimal("0")
        nanos = _safe_decimal(money.get("nanos")) or Decimal("0")
        return units + (nanos / Decimal("1000000000"))

    @staticmethod
    def _mid_price_from_range(price_range: Dict[str, Any] | None) -> Decimal | None:
        if not isinstance(price_range, dict):
            return None
        start_price = LocalCostProvider._money_to_decimal(price_range.get("startPrice"))
        end_price = LocalCostProvider._money_to_decimal(price_range.get("endPrice"))
        if start_price is None and end_price is None:
            return None
        if start_price is not None and end_price is not None and end_price > start_price:
            return (start_price + end_price) / Decimal("2")
        if start_price is not None:
            return start_price * Decimal("1.30")
        if end_price is not None:
            return end_price
        return None

    @staticmethod
    def _price_level_coeff(level: str | None) -> Decimal:
        price_map = {
            "PRICE_LEVEL_FREE": Decimal("0.5"),
            "PRICE_LEVEL_INEXPENSIVE": Decimal("1.0"),
            "PRICE_LEVEL_MODERATE": Decimal("2.0"),
            "PRICE_LEVEL_EXPENSIVE": Decimal("3.0"),
            "PRICE_LEVEL_VERY_EXPENSIVE": Decimal("4.0"),
        }
        return price_map.get((level or "").strip(), Decimal("1.8"))

    def _places_text_search(
        self,
        text_query: str,
        max_result_count: int,
    ) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY (or GOOGLE_MAPS_API_KEY) is missing.")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.primaryType,places.priceLevel,places.priceRange,places.rating",
        }
        try:
            response = _http_request_json(
                method="POST",
                url=self.base_url,
                headers=headers,
                payload={
                    "textQuery": text_query,
                    "maxResultCount": max_result_count,
                },
            )
            places = response.get("places", [])
            return places if isinstance(places, list) else []
        except Exception as e:
            print(f"Google Places API request failed: {e}")
            return []

    def _extract_costs(
        self,
        places: List[Dict[str, Any]],
        base_anchor: Decimal,
    ) -> List[Decimal]:
        # priceRange is intentionally ignored: Google returns it in local currency
        # with no reliable conversion, so treating it as USD gives absurd results
        # (e.g. 2000 EGP for a Cairo restaurant reads as $2000). priceLevel is a
        # market-relative categorical label and is currency-agnostic.
        values: List[Decimal] = []
        for place in places:
            if not isinstance(place, dict):
                continue
            coeff = self._price_level_coeff(place.get("priceLevel"))
            values.append(base_anchor * coeff)
        return [v for v in values if v > 0]

    # Fixed daily public-transit estimates per tier. Places API "transport" searches
    # return tour operators and private car services, not per-ride fares, so these
    # are hardcoded. All tiers represent public transit (bus/metro/tram); luxury
    # adds frequent taxi use on top of transit — no private car rental included.
    _DAILY_TRANSPORT = {
        "cheapest": Decimal("3"),    # bus / metro with transfers
        "affordable": Decimal("6"),  # metro daily pass
        "moderate": Decimal("10"),   # metro + occasional taxi
        "luxury": Decimal("18"),     # frequent taxi + premium transit
    }

    def fetch_daily_tier_costs(
        self, destination_city: str, destination_country: str, currency: str
    ) -> Dict[str, Decimal]:
        if not self.base_url:
            raise ValueError("GOOGLE_PLACES_TEXT_SEARCH_URL is missing.")

        city_query = f"{destination_city}, {destination_country}"
        restaurants = self._places_text_search(f"restaurants in {city_query}", 20)
        cafes = self._places_text_search(f"cafes in {city_query}", 20)

        # Transport is excluded from Places queries: the API surfaces tour operators
        # and private car services whose prices are not per-ride transit fares.
        food_values = self._extract_costs(restaurants + cafes, base_anchor=Decimal("10"))

        if not food_values:
            raise ValueError("Google Places returned no usable local-living signals.")

        food_pool = sorted(food_values)

        food_cheapest = _tier_value_from_sorted(food_pool, Decimal("0.15"))
        food_affordable = _tier_value_from_sorted(food_pool, Decimal("0.40"))
        food_moderate = _tier_value_from_sorted(food_pool, Decimal("0.60"))
        food_luxury = _tier_value_from_sorted(food_pool, Decimal("0.90"))

        t = self._DAILY_TRANSPORT
        # Daily per-traveler local costs (meals + local transport + incidentals).
        tiers = {
            "cheapest": (food_cheapest * Decimal("1.7"))
            + t["cheapest"]
            + Decimal("6"),
            "affordable": (food_affordable * Decimal("2.0"))
            + t["affordable"]
            + Decimal("10"),
            "moderate": (food_moderate * Decimal("2.3"))
            + t["moderate"]
            + Decimal("16"),
            "luxury": (food_luxury * Decimal("2.8"))
            + t["luxury"]
            + Decimal("28"),
        }

        ordered: Dict[str, Decimal] = {}
        last_value = Decimal("0")
        for tier in TIER_ORDER:
            value = tiers[tier]
            if value < last_value:
                value = last_value
            ordered[tier] = value
            last_value = value
        return ordered


class GoogleWeatherProvider:
    def __init__(self):
        self.api_key = getattr(settings, "GOOGLE_WEATHER_API_KEY", "")
        self.base_url = getattr(
            settings,
            "GOOGLE_WEATHER_BASE_URL",
            "https://weather.googleapis.com/v1/forecast/days:lookup",
        )
        self.geonames_username = getattr(settings, "GEONAMES_USERNAME", "")

    def _geocode(self, city: str, country: str) -> tuple[float, float]:
        if not self.geonames_username:
            raise ValueError("GEONAMES_USERNAME is required for weather geocoding.")
        data = _http_request_json(
            "GET",
            "https://secure.geonames.org/searchJSON",
            params={
                "q": f"{city}, {country}",
                "maxRows": "1",
                "username": self.geonames_username,
                "lang": "en",
                "style": "SHORT",
                "featureClass": "P",
            },
        )
        places = data.get("geonames", [])
        if not places:
            raise ValueError(f"Cannot geocode '{city}, {country}'.")
        return float(places[0]["lat"]), float(places[0]["lng"])

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


def fetch_destination_weather(
    destination_city: str,
    destination_country: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict[str, Any]:
    return GoogleWeatherProvider().fetch_summary(
        destination_city, destination_country, start_date, end_date
    )


def _normalize_duration_days(departure_date: str, return_date: str) -> int:
    departure = _parse_date(departure_date)
    returning = _parse_date(return_date)
    days = (returning - departure).days
    if days <= 0:
        raise ValueError("return_date must be after departure_date.")
    return days


def build_dynamic_tier_quotes(input_data: DynamicPricingInput) -> DynamicTierQuoteResult:
    if input_data.adults <= 0:
        raise ValueError("adults must be greater than zero.")

    trip_duration_days = _normalize_duration_days(
        input_data.departure_date,
        input_data.return_date,
    )

    flight_provider = SerpApiFlightProvider()
    hotel_provider = SerpApiHotelProvider()
    local_provider = LocalCostProvider()

    try:
        flight_tiers = flight_provider.fetch_tier_prices(
            origin_city=input_data.origin_city,
            destination_city=input_data.destination_city,
            departure_date=input_data.departure_date,
            return_date=input_data.return_date,
            adults=input_data.adults,
            currency=input_data.currency,
        )
    except Exception:
        # Fallback to single-query distribution when segmented fetch cannot complete.
        flight_prices = flight_provider.fetch_prices(
            origin_city=input_data.origin_city,
            destination_city=input_data.destination_city,
            departure_date=input_data.departure_date,
            return_date=input_data.return_date,
            adults=input_data.adults,
            currency=input_data.currency,
        )
        flight_tiers = _map_values_to_tiers(flight_prices)

    try:
        hotel_tiers = hotel_provider.fetch_tier_prices(
            destination_city=input_data.destination_city,
            destination_country=input_data.destination_country,
            check_in=input_data.departure_date,
            check_out=input_data.return_date,
            adults=input_data.adults,
            currency=input_data.currency,
        )
    except Exception:
        hotel_prices = hotel_provider.fetch_prices(
            destination_city=input_data.destination_city,
            destination_country=input_data.destination_country,
            check_in=input_data.departure_date,
            check_out=input_data.return_date,
            adults=input_data.adults,
            currency=input_data.currency,
            trip_duration_days=trip_duration_days,
        )
        hotel_tiers = _map_values_to_tiers(hotel_prices)

    local_tiers = local_provider.fetch_daily_tier_costs(
        destination_city=input_data.destination_city,
        destination_country=input_data.destination_country,
        currency=input_data.currency,
    )
    tiers: Dict[str, TierCostBreakdown] = {}
    duration_decimal = Decimal(trip_duration_days)
    for tier in TIER_ORDER:
        flight_cost = flight_tiers[tier]
        hotel_daily = hotel_tiers[tier]
        local_daily = local_tiers[tier]
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
            "flights": "serpapi_google_flights",
            "hotels": "serpapi_google_hotels",
            "local_costs": "google_places_text_search",
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

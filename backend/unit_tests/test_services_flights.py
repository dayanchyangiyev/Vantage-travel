"""
test_services_flights.py — Unit tests for SerpApiFlightProvider.

All HTTP calls are intercepted using pytest-mock (mocker.patch).
The real SerpAPI is never contacted — we feed in the fixture payloads
defined in conftest.py and verify the parsing logic is correct.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch

from trips.services import (
    SerpApiFlightProvider,
    _map_values_to_tiers,
    TIER_ORDER,
)


@pytest.fixture
def flight_provider(settings):
    """Return a SerpApiFlightProvider with fake credentials."""
    settings.SERPAPI_API_KEY = "fake-key"
    settings.SERPAPI_BASE_URL = "https://serpapi.com/search.json"
    return SerpApiFlightProvider()


# ---------------------------------------------------------------------------
# fetch_prices — reads best_flights + other_flights keys
# ---------------------------------------------------------------------------

class TestFetchPrices:
    def test_extracts_prices_from_best_and_other_flights(
        self, flight_provider, serpapi_flights_response, mocker
    ):
        # Patch the low-level HTTP function so no real request is made
        mocker.patch(
            "trips.services._http_request_json",
            return_value=serpapi_flights_response,
        )
        # Also patch airport code resolution to return a fixed IATA code
        mocker.patch.object(
            flight_provider, "_resolve_location_to_airport", return_value="JFK"
        )

        prices = flight_provider.fetch_prices(
            origin_city="New York",
            destination_city="London",
            departure_date="2025-06-01",
            return_date="2025-06-10",
            adults=1,
            currency="USD",
        )

        assert len(prices) == 5  # 2 best + 3 other
        assert Decimal("350") in prices
        assert Decimal("280") in prices

    def test_falls_back_to_numeric_candidates_when_no_price_key(
        self, flight_provider, mocker
    ):
        """If neither best_flights nor other_flights has a 'price' key,
        fall back to scanning the whole response for any price-like number."""
        fallback_response = {
            "search_metadata": {},
            "price_insights": {"lowest_price": 199},
        }
        mocker.patch(
            "trips.services._http_request_json",
            return_value=fallback_response,
        )
        mocker.patch.object(
            flight_provider, "_resolve_location_to_airport", return_value="JFK"
        )

        prices = flight_provider.fetch_prices(
            origin_city="NYC",
            destination_city="LAX",
            departure_date="2025-07-01",
            return_date="2025-07-08",
            adults=1,
            currency="USD",
        )
        assert len(prices) > 0

    def test_raises_when_no_prices_at_all(self, flight_provider, mocker):
        mocker.patch(
            "trips.services._http_request_json",
            return_value={"search_metadata": {}},  # completely empty
        )
        mocker.patch.object(
            flight_provider, "_resolve_location_to_airport", return_value="JFK"
        )

        with pytest.raises(ValueError, match="no usable flight prices"):
            flight_provider.fetch_prices(
                origin_city="NYC",
                destination_city="LAX",
                departure_date="2025-07-01",
                return_date="2025-07-08",
                adults=1,
                currency="USD",
            )

    def test_prices_are_all_positive(
        self, flight_provider, serpapi_flights_response, mocker
    ):
        mocker.patch(
            "trips.services._http_request_json",
            return_value=serpapi_flights_response,
        )
        mocker.patch.object(
            flight_provider, "_resolve_location_to_airport", return_value="JFK"
        )

        prices = flight_provider.fetch_prices(
            origin_city="NYC",
            destination_city="LHR",
            departure_date="2025-06-01",
            return_date="2025-06-15",
            adults=2,
            currency="GBP",
        )
        assert all(p > 0 for p in prices)


# ---------------------------------------------------------------------------
# fetch_tier_prices — produces 4 non-decreasing tier values
# ---------------------------------------------------------------------------

class TestFetchTierPrices:
    def _make_tier_response(self, prices):
        """Helper: build a minimal SerpAPI-like response for given prices."""
        return {
            "best_flights": [{"price": p} for p in prices],
        }

    def test_returns_all_four_tiers(self, flight_provider, mocker):
        response = self._make_tier_response([200, 350, 500, 800, 1200])
        mocker.patch(
            "trips.services._http_request_json",
            return_value=response,
        )
        mocker.patch.object(
            flight_provider, "_resolve_location_to_airport", return_value="JFK"
        )

        tiers = flight_provider.fetch_tier_prices(
            origin_city="NYC",
            destination_city="PAR",
            departure_date="2025-09-01",
            return_date="2025-09-10",
            adults=1,
            currency="USD",
        )

        assert set(tiers.keys()) == {"cheapest", "affordable", "moderate", "luxury"}

    def test_tiers_are_non_decreasing(self, flight_provider, mocker):
        response = self._make_tier_response([150, 300, 600, 1000, 2500])
        mocker.patch(
            "trips.services._http_request_json",
            return_value=response,
        )
        mocker.patch.object(
            flight_provider, "_resolve_location_to_airport", return_value="JFK"
        )

        tiers = flight_provider.fetch_tier_prices(
            origin_city="NYC",
            destination_city="TYO",
            departure_date="2025-10-01",
            return_date="2025-10-14",
            adults=1,
            currency="USD",
        )

        for i in range(len(TIER_ORDER) - 1):
            assert tiers[TIER_ORDER[i]] <= tiers[TIER_ORDER[i + 1]], (
                f"{TIER_ORDER[i]} should be <= {TIER_ORDER[i + 1]}"
            )

    def test_raises_when_all_tier_queries_fail(self, flight_provider, mocker):
        """If every segmented search raises an exception, raise ValueError."""
        mocker.patch(
            "trips.services._http_request_json",
            side_effect=Exception("network error"),
        )
        mocker.patch.object(
            flight_provider, "_resolve_location_to_airport", return_value="JFK"
        )

        with pytest.raises(ValueError, match="no usable segmented prices"):
            flight_provider.fetch_tier_prices(
                origin_city="NYC",
                destination_city="DXB",
                departure_date="2025-11-01",
                return_date="2025-11-08",
                adults=1,
                currency="USD",
            )


# ---------------------------------------------------------------------------
# _resolve_location_to_airport — city name → IATA code resolution
# ---------------------------------------------------------------------------

class TestResolveLocationToAirport:
    def test_iata_code_passthrough(self, flight_provider):
        """A 3-letter code is returned immediately without calling the API."""
        result = flight_provider._resolve_location_to_airport("JFK")
        assert result == "JFK"

    def test_city_name_triggers_autocomplete(
        self, flight_provider, serpapi_autocomplete_response, mocker
    ):
        mock_search = mocker.patch.object(
            flight_provider.client, "search", return_value=serpapi_autocomplete_response
        )
        result = flight_provider._resolve_location_to_airport("New York")
        mock_search.assert_called_once()
        assert result == "JFK"

    def test_raises_when_no_iata_code_in_autocomplete(self, flight_provider, mocker):
        mocker.patch.object(
            flight_provider.client, "search", return_value={"airports": []}
        )
        with pytest.raises(ValueError, match="Unable to resolve"):
            flight_provider._resolve_location_to_airport("Nowhere City")

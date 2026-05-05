"""
test_services_hotels.py — Unit tests for SerpApiHotelProvider.

All HTTP calls are mocked. Tests verify that:
  - Prices are extracted from the correct JSON fields
  - The fallback chain (rate_per_night → extracted_price → ads) works
  - Tier values are monotonically non-decreasing
  - Appropriate errors are raised when no prices are found
"""

import pytest
from decimal import Decimal

from trips.services import SerpApiHotelProvider, TIER_ORDER


@pytest.fixture
def hotel_provider(settings):
    settings.SERPAPI_API_KEY = "fake-key"
    settings.SERPAPI_BASE_URL = "https://serpapi.com/search.json"
    return SerpApiHotelProvider()


# ---------------------------------------------------------------------------
# fetch_prices — price extraction from various response shapes
# ---------------------------------------------------------------------------

class TestHotelFetchPrices:
    def test_extracts_rate_per_night_extracted_lowest(
        self, hotel_provider, serpapi_hotels_response, mocker
    ):
        mocker.patch(
            "trips.services._http_request_json",
            return_value=serpapi_hotels_response,
        )
        prices = hotel_provider.fetch_prices(
            destination_city="Paris",
            destination_country="France",
            check_in="2025-06-01",
            check_out="2025-06-08",
            adults=2,
            currency="USD",
            trip_duration_days=7,
        )
        assert Decimal("85") in prices
        assert Decimal("120") in prices

    def test_extracts_from_ads_section(self, hotel_provider, mocker):
        response = {
            "properties": [],
            "ads": [{"extracted_price": 65}, {"extracted_price": 95}],
        }
        mocker.patch("trips.services._http_request_json", return_value=response)

        prices = hotel_provider.fetch_prices(
            destination_city="Berlin",
            destination_country="Germany",
            check_in="2025-07-01",
            check_out="2025-07-07",
            adults=1,
            currency="EUR",
            trip_duration_days=6,
        )
        assert Decimal("65") in prices
        assert Decimal("95") in prices

    def test_falls_back_to_extracted_price_field(self, hotel_provider, mocker):
        response = {
            "properties": [
                {"extracted_price": 175},
                {"extracted_price": 220},
            ],
            "ads": [],
        }
        mocker.patch("trips.services._http_request_json", return_value=response)

        prices = hotel_provider.fetch_prices(
            destination_city="Tokyo",
            destination_country="Japan",
            check_in="2025-08-10",
            check_out="2025-08-17",
            adults=1,
            currency="JPY",
            trip_duration_days=7,
        )
        assert Decimal("175") in prices

    def test_raises_when_no_prices(self, hotel_provider, mocker):
        mocker.patch(
            "trips.services._http_request_json",
            return_value={"properties": [], "ads": []},
        )
        with pytest.raises(ValueError, match="no usable hotel prices"):
            hotel_provider.fetch_prices(
                destination_city="Nowhere",
                destination_country="Void",
                check_in="2025-09-01",
                check_out="2025-09-05",
                adults=1,
                currency="USD",
                trip_duration_days=4,
            )

    def test_all_prices_are_positive(
        self, hotel_provider, serpapi_hotels_response, mocker
    ):
        mocker.patch("trips.services._http_request_json", return_value=serpapi_hotels_response)

        prices = hotel_provider.fetch_prices(
            destination_city="Rome",
            destination_country="Italy",
            check_in="2025-05-15",
            check_out="2025-05-22",
            adults=2,
            currency="EUR",
            trip_duration_days=7,
        )
        assert all(p > 0 for p in prices)


# ---------------------------------------------------------------------------
# fetch_tier_prices — 4 non-decreasing tier buckets
# ---------------------------------------------------------------------------

class TestHotelFetchTierPrices:
    def _make_hotel_response(self, prices):
        return {
            "properties": [{"rate_per_night": {"extracted_lowest": p}} for p in prices],
            "ads": [],
        }

    def test_returns_all_four_tiers(self, hotel_provider, mocker):
        response = self._make_hotel_response([50, 100, 200, 350, 600])
        mocker.patch("trips.services._http_request_json", return_value=response)

        tiers = hotel_provider.fetch_tier_prices(
            destination_city="Barcelona",
            destination_country="Spain",
            check_in="2025-06-01",
            check_out="2025-06-08",
            adults=2,
            currency="EUR",
        )
        assert set(tiers.keys()) == {"cheapest", "affordable", "moderate", "luxury"}

    def test_tiers_are_non_decreasing(self, hotel_provider, mocker):
        response = self._make_hotel_response([60, 90, 150, 300, 500, 800])
        mocker.patch("trips.services._http_request_json", return_value=response)

        tiers = hotel_provider.fetch_tier_prices(
            destination_city="Amsterdam",
            destination_country="Netherlands",
            check_in="2025-07-01",
            check_out="2025-07-07",
            adults=1,
            currency="EUR",
        )

        for i in range(len(TIER_ORDER) - 1):
            assert tiers[TIER_ORDER[i]] <= tiers[TIER_ORDER[i + 1]]

    def test_raises_when_all_queries_fail(self, hotel_provider, mocker):
        mocker.patch(
            "trips.services._http_request_json",
            side_effect=Exception("API down"),
        )
        with pytest.raises(ValueError, match="no usable segmented prices"):
            hotel_provider.fetch_tier_prices(
                destination_city="Nowhere",
                destination_country="Void",
                check_in="2025-08-01",
                check_out="2025-08-05",
                adults=1,
                currency="USD",
            )

    def test_tier_values_are_decimal_type(self, hotel_provider, mocker):
        response = self._make_hotel_response([80, 130, 200, 400])
        mocker.patch("trips.services._http_request_json", return_value=response)

        tiers = hotel_provider.fetch_tier_prices(
            destination_city="Lisbon",
            destination_country="Portugal",
            check_in="2025-09-01",
            check_out="2025-09-07",
            adults=1,
            currency="EUR",
        )
        for tier_name in TIER_ORDER:
            assert isinstance(tiers[tier_name], Decimal)

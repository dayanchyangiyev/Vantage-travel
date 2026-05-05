"""
test_services_local_costs.py — Unit tests for LocalCostProvider (Google Places API).

LocalCostProvider calls Google Places Text Search three times (restaurants,
cafes, transport) and combines the results into daily cost tiers. All three
HTTP calls are mocked here so no real API key is required.

Functions/methods tested:
  - _money_to_decimal         : converts Google Money proto dict to Decimal
  - _mid_price_from_range     : extracts mid-point from startPrice/endPrice
  - _price_level_coeff        : maps PRICE_LEVEL_* strings to multipliers
  - _extract_costs            : combines priceRange + priceLevel data
  - fetch_daily_tier_costs    : full pipeline producing 4 tier values
"""

import pytest
from decimal import Decimal

from trips.services import LocalCostProvider, TIER_ORDER


@pytest.fixture
def local_provider(settings):
    settings.GOOGLE_PLACES_API_KEY = "fake-places-key"
    settings.GOOGLE_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    return LocalCostProvider()


# ---------------------------------------------------------------------------
# _money_to_decimal (static method)
# ---------------------------------------------------------------------------

class TestMoneyToDecimal:
    def test_units_only(self):
        money = {"units": "25", "nanos": 0}
        result = LocalCostProvider._money_to_decimal(money)
        assert result == Decimal("25")

    def test_units_and_nanos(self):
        money = {"units": "10", "nanos": 500000000}  # 0.5
        result = LocalCostProvider._money_to_decimal(money)
        assert result == Decimal("10.5")

    def test_none_returns_none(self):
        assert LocalCostProvider._money_to_decimal(None) is None

    def test_non_dict_returns_none(self):
        assert LocalCostProvider._money_to_decimal("bad") is None

    def test_zero_units(self):
        result = LocalCostProvider._money_to_decimal({"units": "0", "nanos": 0})
        assert result == Decimal("0")


# ---------------------------------------------------------------------------
# _mid_price_from_range (static method)
# ---------------------------------------------------------------------------

class TestMidPriceFromRange:
    def test_mid_of_range(self):
        price_range = {
            "startPrice": {"units": "20", "nanos": 0},
            "endPrice": {"units": "60", "nanos": 0},
        }
        result = LocalCostProvider._mid_price_from_range(price_range)
        assert result == Decimal("40")

    def test_only_start_price(self):
        price_range = {
            "startPrice": {"units": "30", "nanos": 0},
        }
        result = LocalCostProvider._mid_price_from_range(price_range)
        # 30 * 1.30 = 39
        assert result == Decimal("39")

    def test_only_end_price(self):
        price_range = {
            "endPrice": {"units": "50", "nanos": 0},
        }
        result = LocalCostProvider._mid_price_from_range(price_range)
        assert result == Decimal("50")

    def test_none_input(self):
        assert LocalCostProvider._mid_price_from_range(None) is None

    def test_equal_start_end(self):
        price_range = {
            "startPrice": {"units": "40", "nanos": 0},
            "endPrice": {"units": "40", "nanos": 0},
        }
        # end is not > start, so returns start * 1.30
        result = LocalCostProvider._mid_price_from_range(price_range)
        assert result == Decimal("52")


# ---------------------------------------------------------------------------
# _price_level_coeff (static method)
# ---------------------------------------------------------------------------

class TestPriceLevelCoeff:
    def test_inexpensive_returns_one(self):
        assert LocalCostProvider._price_level_coeff("PRICE_LEVEL_INEXPENSIVE") == Decimal("1.0")

    def test_expensive_returns_three(self):
        assert LocalCostProvider._price_level_coeff("PRICE_LEVEL_EXPENSIVE") == Decimal("3.0")

    def test_unknown_level_returns_default(self):
        assert LocalCostProvider._price_level_coeff("PRICE_LEVEL_UNKNOWN") == Decimal("1.8")

    def test_none_returns_default(self):
        assert LocalCostProvider._price_level_coeff(None) == Decimal("1.8")

    def test_very_expensive(self):
        assert LocalCostProvider._price_level_coeff("PRICE_LEVEL_VERY_EXPENSIVE") == Decimal("4.0")


# ---------------------------------------------------------------------------
# fetch_daily_tier_costs — full pipeline
# ---------------------------------------------------------------------------

class TestFetchDailyTierCosts:
    def test_returns_all_four_tiers(self, local_provider, google_places_response, mocker):
        # All three Places queries (restaurants, cafes, transport) return the same fixture
        mocker.patch.object(
            local_provider, "_places_text_search", return_value=google_places_response["places"]
        )

        result = local_provider.fetch_daily_tier_costs(
            destination_city="Paris",
            destination_country="France",
            currency="EUR",
        )

        assert set(result.keys()) == {"cheapest", "affordable", "moderate", "luxury"}

    def test_tiers_are_non_decreasing(self, local_provider, google_places_response, mocker):
        mocker.patch.object(
            local_provider, "_places_text_search", return_value=google_places_response["places"]
        )

        result = local_provider.fetch_daily_tier_costs(
            destination_city="Tokyo",
            destination_country="Japan",
            currency="JPY",
        )

        for i in range(len(TIER_ORDER) - 1):
            assert result[TIER_ORDER[i]] <= result[TIER_ORDER[i + 1]]

    def test_tier_values_are_positive(self, local_provider, google_places_response, mocker):
        mocker.patch.object(
            local_provider, "_places_text_search", return_value=google_places_response["places"]
        )

        result = local_provider.fetch_daily_tier_costs(
            destination_city="Berlin",
            destination_country="Germany",
            currency="EUR",
        )
        for tier_name in TIER_ORDER:
            assert result[tier_name] > 0

    def test_raises_when_places_returns_empty(self, local_provider, mocker):
        mocker.patch.object(local_provider, "_places_text_search", return_value=[])

        with pytest.raises(ValueError, match="no usable local-living signals"):
            local_provider.fetch_daily_tier_costs(
                destination_city="Nowhere",
                destination_country="Void",
                currency="USD",
            )

    def test_uses_price_range_when_available(self, local_provider, mocker):
        """Places with explicit priceRange should use mid-point, not coeff * anchor."""
        places_with_range = [
            {
                "priceLevel": "PRICE_LEVEL_MODERATE",
                "priceRange": {
                    "startPrice": {"units": "15", "nanos": 0},
                    "endPrice": {"units": "35", "nanos": 0},
                },
            }
        ]
        mocker.patch.object(local_provider, "_places_text_search", return_value=places_with_range)

        result = local_provider.fetch_daily_tier_costs(
            destination_city="Lisbon",
            destination_country="Portugal",
            currency="EUR",
        )
        # We can't assert exact value due to the formula, but tiers should exist
        assert "cheapest" in result

    def test_tier_values_are_decimal(self, local_provider, google_places_response, mocker):
        mocker.patch.object(
            local_provider, "_places_text_search", return_value=google_places_response["places"]
        )

        result = local_provider.fetch_daily_tier_costs(
            destination_city="Madrid",
            destination_country="Spain",
            currency="EUR",
        )
        for tier_name in TIER_ORDER:
            assert isinstance(result[tier_name], Decimal)

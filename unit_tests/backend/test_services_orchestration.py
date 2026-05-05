"""
test_services_orchestration.py — Integration-style tests for the high-level
service functions that coordinate flights, hotels, and local costs.

Functions tested:
  - build_dynamic_tier_quotes   : assembles full pricing quote from all 3 providers
  - evaluate_dynamic_budget     : decides if a budget is feasible for a trip

All three provider classes (SerpApiFlightProvider, SerpApiHotelProvider,
LocalCostProvider) are mocked so we control exactly what data each returns.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from trips.services import (
    DynamicPricingInput,
    build_dynamic_tier_quotes,
    evaluate_dynamic_budget,
    TIER_ORDER,
)


# ---------------------------------------------------------------------------
# Shared test input
# ---------------------------------------------------------------------------

@pytest.fixture
def pricing_input():
    return DynamicPricingInput(
        origin_city="New York",
        destination_city="Paris",
        destination_country="France",
        departure_date="2025-09-01",
        return_date="2025-09-08",   # 7 days
        adults=2,
        max_flight_budget=Decimal("1500"),
        total_living_budget=Decimal("2000"),
        comfort_preference="affordable",
        currency="USD",
    )


@pytest.fixture
def mock_flight_tiers():
    return {
        "cheapest": Decimal("300"),
        "affordable": Decimal("450"),
        "moderate": Decimal("700"),
        "luxury": Decimal("1200"),
    }


@pytest.fixture
def mock_hotel_tiers():
    return {
        "cheapest": Decimal("60"),
        "affordable": Decimal("100"),
        "moderate": Decimal("180"),
        "luxury": Decimal("350"),
    }


@pytest.fixture
def mock_local_tiers():
    return {
        "cheapest": Decimal("30"),
        "affordable": Decimal("55"),
        "moderate": Decimal("80"),
        "luxury": Decimal("140"),
    }


# ---------------------------------------------------------------------------
# build_dynamic_tier_quotes
# ---------------------------------------------------------------------------

class TestBuildDynamicTierQuotes:
    def _patch_providers(self, mocker, flight_tiers, hotel_tiers, local_tiers):
        mocker.patch(
            "trips.services.SerpApiFlightProvider.fetch_tier_prices",
            return_value=flight_tiers,
        )
        mocker.patch(
            "trips.services.SerpApiHotelProvider.fetch_tier_prices",
            return_value=hotel_tiers,
        )
        mocker.patch(
            "trips.services.LocalCostProvider.fetch_daily_tier_costs",
            return_value=local_tiers,
        )

    def test_result_has_correct_keys(
        self, mocker, pricing_input, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        result = build_dynamic_tier_quotes(pricing_input)

        assert "destination_city" in result
        assert "destination_country" in result
        assert "trip_duration_days" in result
        assert "currency" in result
        assert "tiers" in result
        assert "sources" in result

    def test_trip_duration_is_correct(
        self, mocker, pricing_input, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        result = build_dynamic_tier_quotes(pricing_input)
        assert result["trip_duration_days"] == 7

    def test_all_four_tiers_present(
        self, mocker, pricing_input, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        result = build_dynamic_tier_quotes(pricing_input)
        assert set(result["tiers"].keys()) == {"cheapest", "affordable", "moderate", "luxury"}

    def test_each_tier_breakdown_has_required_fields(
        self, mocker, pricing_input, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        result = build_dynamic_tier_quotes(pricing_input)
        required = {
            "flight_cost",
            "hotel_daily_cost",
            "local_daily_cost",
            "total_daily_living_cost",
            "total_living_cost",
            "total_trip_cost",
        }
        for tier_name in TIER_ORDER:
            assert required.issubset(set(result["tiers"][tier_name].keys()))

    def test_total_trip_cost_formula(
        self, mocker, pricing_input, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        """total_trip_cost = flight_cost + (hotel_daily + local_daily) * days"""
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        result = build_dynamic_tier_quotes(pricing_input)

        tier = result["tiers"]["affordable"]
        expected_total = (
            mock_flight_tiers["affordable"]
            + (mock_hotel_tiers["affordable"] + mock_local_tiers["affordable"]) * Decimal("7")
        )
        assert abs(Decimal(str(tier["total_trip_cost"])) - expected_total) < Decimal("0.01")

    def test_sources_map_correct_providers(
        self, mocker, pricing_input, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        result = build_dynamic_tier_quotes(pricing_input)
        assert result["sources"]["flights"] == "serpapi_google_flights"
        assert result["sources"]["hotels"] == "serpapi_google_hotels"
        assert result["sources"]["local_costs"] == "google_places_text_search"

    def test_zero_adults_raises(self, mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        bad_input = DynamicPricingInput(
            origin_city="NYC",
            destination_city="PAR",
            destination_country="France",
            departure_date="2025-09-01",
            return_date="2025-09-08",
            adults=0,  # invalid
            max_flight_budget=Decimal("1000"),
            total_living_budget=Decimal("2000"),
            comfort_preference="affordable",
            currency="USD",
        )
        with pytest.raises(ValueError, match="adults must be greater than zero"):
            build_dynamic_tier_quotes(bad_input)

    def test_return_before_departure_raises(
        self, mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        bad_input = DynamicPricingInput(
            origin_city="NYC",
            destination_city="PAR",
            destination_country="France",
            departure_date="2025-09-08",
            return_date="2025-09-01",   # before departure!
            adults=1,
            max_flight_budget=Decimal("1000"),
            total_living_budget=Decimal("2000"),
            comfort_preference="affordable",
            currency="USD",
        )
        with pytest.raises(ValueError, match="return_date must be after"):
            build_dynamic_tier_quotes(bad_input)


# ---------------------------------------------------------------------------
# evaluate_dynamic_budget
# ---------------------------------------------------------------------------

class TestEvaluateDynamicBudget:
    def _patch_providers(self, mocker, flight_tiers, hotel_tiers, local_tiers):
        mocker.patch(
            "trips.services.SerpApiFlightProvider.fetch_tier_prices",
            return_value=flight_tiers,
        )
        mocker.patch(
            "trips.services.SerpApiHotelProvider.fetch_tier_prices",
            return_value=hotel_tiers,
        )
        mocker.patch(
            "trips.services.LocalCostProvider.fetch_daily_tier_costs",
            return_value=local_tiers,
        )

    def test_feasible_when_budget_exceeds_cost(
        self, mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        # affordable tier: hotel=100, local=55 → daily=155, 7 days = 1085 total living
        # budget = 2000 > 1085 → feasible
        generous_input = DynamicPricingInput(
            origin_city="NYC",
            destination_city="Paris",
            destination_country="France",
            departure_date="2025-09-01",
            return_date="2025-09-08",
            adults=1,
            max_flight_budget=Decimal("500"),
            total_living_budget=Decimal("2000"),   # generous budget
            comfort_preference="affordable",
            currency="USD",
        )
        result = evaluate_dynamic_budget(generous_input)
        assert result["feasible"] is True
        assert result["metrics"]["total_shortfall"] == 0.0

    def test_infeasible_when_budget_too_low(
        self, mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        # affordable daily = 100+55 = 155, 7 days = 1085 needed, we give only 500
        tight_input = DynamicPricingInput(
            origin_city="NYC",
            destination_city="Paris",
            destination_country="France",
            departure_date="2025-09-01",
            return_date="2025-09-08",
            adults=1,
            max_flight_budget=Decimal("500"),
            total_living_budget=Decimal("500"),   # insufficient
            comfort_preference="affordable",
            currency="USD",
        )
        result = evaluate_dynamic_budget(tight_input)
        assert result["feasible"] is False
        assert result["metrics"]["total_shortfall"] > 0

    def test_infeasible_result_includes_suggestion(
        self, mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        tight_input = DynamicPricingInput(
            origin_city="NYC",
            destination_city="Paris",
            destination_country="France",
            departure_date="2025-09-01",
            return_date="2025-09-08",
            adults=1,
            max_flight_budget=Decimal("500"),
            total_living_budget=Decimal("300"),
            comfort_preference="affordable",
            currency="USD",
        )
        result = evaluate_dynamic_budget(tight_input)
        assert result["suggestions"]["optimized_duration_days"] is not None
        assert result["suggestions"]["message"] is not None

    def test_invalid_comfort_preference_raises(
        self, mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        bad_input = DynamicPricingInput(
            origin_city="NYC",
            destination_city="Paris",
            destination_country="France",
            departure_date="2025-09-01",
            return_date="2025-09-08",
            adults=1,
            max_flight_budget=Decimal("500"),
            total_living_budget=Decimal("2000"),
            comfort_preference="super_deluxe",   # not a valid tier
            currency="USD",
        )
        with pytest.raises(ValueError, match="Unsupported comfort_preference"):
            evaluate_dynamic_budget(bad_input)

    def test_result_contains_pricing_snapshot(
        self, mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers
    ):
        self._patch_providers(mocker, mock_flight_tiers, mock_hotel_tiers, mock_local_tiers)
        input_data = DynamicPricingInput(
            origin_city="NYC",
            destination_city="Paris",
            destination_country="France",
            departure_date="2025-09-01",
            return_date="2025-09-08",
            adults=1,
            max_flight_budget=Decimal("500"),
            total_living_budget=Decimal("2000"),
            comfort_preference="moderate",
            currency="USD",
        )
        result = evaluate_dynamic_budget(input_data)
        assert "pricing_snapshot" in result
        assert "tiers" in result["pricing_snapshot"]

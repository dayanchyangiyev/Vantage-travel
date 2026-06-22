"""
test_services_orchestration.py — Integration-style tests for the high-level
service functions that assemble the 4-tier trip budget from the LiteAPI
(Nuitee) flight and hotel option searches.

Functions tested:
  - build_dynamic_tier_quotes   : derives per-tier flight/hotel/living costs
  - evaluate_dynamic_budget     : decides if a budget is feasible for a trip

Both Nuitee providers' `search_options` are mocked so we control the option
prices each returns. Living cost is derived from the lodging price, so there is
no third provider to mock.
"""

import pytest
from decimal import Decimal

from trips.services import (
    DynamicPricingInput,
    build_dynamic_tier_quotes,
    evaluate_dynamic_budget,
    TIER_ORDER,
)


# ---------------------------------------------------------------------------
# Shared test input + mock helpers
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


def _flights(cheapest, affordable, moderate, luxury):
    return {
        "origin": "NYC", "destination": "PAR", "currency": "USD",
        "tiers": {
            "cheapest": [{"price": cheapest}],
            "affordable": [{"price": affordable}],
            "moderate": [{"price": moderate}],
            "luxury": [{"price": luxury}],
        },
    }


def _hotels(cheapest, affordable, moderate, luxury):
    # Prices are stay totals (7 nights in these tests).
    return {
        "destination_city": "Paris", "destination_country": "France",
        "currency": "USD", "nights": 7,
        "tiers": {
            "cheapest": [{"price": cheapest}],
            "affordable": [{"price": affordable}],
            "moderate": [{"price": moderate}],
            "luxury": [{"price": luxury}],
        },
    }


def _patch_providers(mocker):
    """Flight tier prices 300/450/700/1200; hotel stay totals 420/700/1260/2450
    → nightly 60/100/180/350 over 7 nights."""
    mocker.patch(
        "trips.services.NuiteeFlightProvider.search_options",
        return_value=_flights(300, 450, 700, 1200),
    )
    mocker.patch(
        "trips.services.NuiteeHotelProvider.search_options",
        return_value=_hotels(420, 700, 1260, 2450),
    )


# ---------------------------------------------------------------------------
# build_dynamic_tier_quotes
# ---------------------------------------------------------------------------

class TestBuildDynamicTierQuotes:
    def test_result_has_correct_keys(self, mocker, pricing_input):
        _patch_providers(mocker)
        result = build_dynamic_tier_quotes(pricing_input)
        for key in ("destination_city", "destination_country", "trip_duration_days",
                    "currency", "tiers", "sources"):
            assert key in result

    def test_trip_duration_is_correct(self, mocker, pricing_input):
        _patch_providers(mocker)
        result = build_dynamic_tier_quotes(pricing_input)
        assert result["trip_duration_days"] == 7

    def test_all_four_tiers_present(self, mocker, pricing_input):
        _patch_providers(mocker)
        result = build_dynamic_tier_quotes(pricing_input)
        assert set(result["tiers"].keys()) == {"cheapest", "affordable", "moderate", "luxury"}

    def test_each_tier_breakdown_has_required_fields(self, mocker, pricing_input):
        _patch_providers(mocker)
        result = build_dynamic_tier_quotes(pricing_input)
        required = {
            "flight_cost", "hotel_daily_cost", "local_daily_cost",
            "total_daily_living_cost", "total_living_cost", "total_trip_cost",
        }
        for tier_name in TIER_ORDER:
            assert required.issubset(set(result["tiers"][tier_name].keys()))

    def test_flight_and_hotel_costs_match_search_prices(self, mocker, pricing_input):
        _patch_providers(mocker)
        result = build_dynamic_tier_quotes(pricing_input)
        affordable = result["tiers"]["affordable"]
        assert affordable["flight_cost"] == 450.0
        # 700 stay total / 7 nights = 100 nightly
        assert affordable["hotel_daily_cost"] == 100.0

    def test_total_trip_cost_is_internally_consistent(self, mocker, pricing_input):
        """total = flight + (hotel_daily + local_daily) * days, with living derived."""
        _patch_providers(mocker)
        result = build_dynamic_tier_quotes(pricing_input)
        tier = result["tiers"]["affordable"]
        days = result["trip_duration_days"]
        expected_daily = tier["hotel_daily_cost"] + tier["local_daily_cost"]
        assert abs(tier["total_daily_living_cost"] - expected_daily) < 0.01
        assert abs(tier["total_living_cost"] - expected_daily * days) < 0.01
        assert abs(tier["total_trip_cost"] - (tier["flight_cost"] + expected_daily * days)) < 0.01

    def test_living_cost_is_derived_and_bounded(self, mocker, pricing_input):
        _patch_providers(mocker)
        result = build_dynamic_tier_quotes(pricing_input)
        # affordable nightly hotel = 100, factor 0.45 → 45 (within floor 30 / cap 120)
        assert result["tiers"]["affordable"]["local_daily_cost"] == 45.0

    def test_totals_are_non_decreasing(self, mocker, pricing_input):
        _patch_providers(mocker)
        result = build_dynamic_tier_quotes(pricing_input)
        totals = [result["tiers"][t]["total_trip_cost"] for t in TIER_ORDER]
        assert totals == sorted(totals)

    def test_sources_map_to_nuitee(self, mocker, pricing_input):
        _patch_providers(mocker)
        result = build_dynamic_tier_quotes(pricing_input)
        assert result["sources"]["flights"] == "nuitee_liteapi_flights"
        assert result["sources"]["hotels"] == "nuitee_liteapi_hotels"
        assert result["sources"]["local_costs"] == "derived_from_lodging"

    def test_empty_flight_tier_is_filled_from_neighbour(self, mocker, pricing_input):
        mocker.patch(
            "trips.services.NuiteeFlightProvider.search_options",
            return_value={"origin": "NYC", "destination": "PAR", "currency": "USD",
                          "tiers": {"cheapest": [{"price": 300}], "affordable": [],
                                    "moderate": [{"price": 700}], "luxury": [{"price": 1200}]}},
        )
        mocker.patch(
            "trips.services.NuiteeHotelProvider.search_options",
            return_value=_hotels(420, 700, 1260, 2450),
        )
        result = build_dynamic_tier_quotes(pricing_input)
        # affordable flight borrows the cheapest tier's price (300).
        assert result["tiers"]["affordable"]["flight_cost"] == 300.0

    def test_zero_adults_raises(self, mocker):
        _patch_providers(mocker)
        bad_input = DynamicPricingInput(
            origin_city="NYC", destination_city="PAR", destination_country="France",
            departure_date="2025-09-01", return_date="2025-09-08", adults=0,
            max_flight_budget=Decimal("1000"), total_living_budget=Decimal("2000"),
            comfort_preference="affordable", currency="USD",
        )
        with pytest.raises(ValueError, match="adults must be greater than zero"):
            build_dynamic_tier_quotes(bad_input)

    def test_return_before_departure_raises(self, mocker):
        _patch_providers(mocker)
        bad_input = DynamicPricingInput(
            origin_city="NYC", destination_city="PAR", destination_country="France",
            departure_date="2025-09-08", return_date="2025-09-01", adults=1,
            max_flight_budget=Decimal("1000"), total_living_budget=Decimal("2000"),
            comfort_preference="affordable", currency="USD",
        )
        with pytest.raises(ValueError, match="return_date must be after"):
            build_dynamic_tier_quotes(bad_input)


# ---------------------------------------------------------------------------
# evaluate_dynamic_budget
# ---------------------------------------------------------------------------

class TestEvaluateDynamicBudget:
    def test_feasible_when_budget_exceeds_cost(self, mocker):
        _patch_providers(mocker)
        # affordable daily = hotel 100 + living 45 = 145; 7 days = 1015 < 2000.
        generous = DynamicPricingInput(
            origin_city="NYC", destination_city="Paris", destination_country="France",
            departure_date="2025-09-01", return_date="2025-09-08", adults=1,
            max_flight_budget=Decimal("500"), total_living_budget=Decimal("2000"),
            comfort_preference="affordable", currency="USD",
        )
        result = evaluate_dynamic_budget(generous)
        assert result["feasible"] is True
        assert result["metrics"]["total_shortfall"] == 0.0

    def test_infeasible_when_budget_too_low(self, mocker):
        _patch_providers(mocker)
        tight = DynamicPricingInput(
            origin_city="NYC", destination_city="Paris", destination_country="France",
            departure_date="2025-09-01", return_date="2025-09-08", adults=1,
            max_flight_budget=Decimal("500"), total_living_budget=Decimal("500"),
            comfort_preference="affordable", currency="USD",
        )
        result = evaluate_dynamic_budget(tight)
        assert result["feasible"] is False
        assert result["metrics"]["total_shortfall"] > 0

    def test_infeasible_result_includes_suggestion(self, mocker):
        _patch_providers(mocker)
        tight = DynamicPricingInput(
            origin_city="NYC", destination_city="Paris", destination_country="France",
            departure_date="2025-09-01", return_date="2025-09-08", adults=1,
            max_flight_budget=Decimal("500"), total_living_budget=Decimal("300"),
            comfort_preference="affordable", currency="USD",
        )
        result = evaluate_dynamic_budget(tight)
        assert result["suggestions"]["optimized_duration_days"] is not None
        assert result["suggestions"]["message"] is not None

    def test_invalid_comfort_preference_raises(self, mocker):
        _patch_providers(mocker)
        bad = DynamicPricingInput(
            origin_city="NYC", destination_city="Paris", destination_country="France",
            departure_date="2025-09-01", return_date="2025-09-08", adults=1,
            max_flight_budget=Decimal("500"), total_living_budget=Decimal("2000"),
            comfort_preference="super_deluxe", currency="USD",
        )
        with pytest.raises(ValueError, match="Unsupported comfort_preference"):
            evaluate_dynamic_budget(bad)

    def test_result_contains_pricing_snapshot(self, mocker):
        _patch_providers(mocker)
        data = DynamicPricingInput(
            origin_city="NYC", destination_city="Paris", destination_country="France",
            departure_date="2025-09-01", return_date="2025-09-08", adults=1,
            max_flight_budget=Decimal("500"), total_living_budget=Decimal("2000"),
            comfort_preference="moderate", currency="USD",
        )
        result = evaluate_dynamic_budget(data)
        assert "pricing_snapshot" in result
        assert "tiers" in result["pricing_snapshot"]

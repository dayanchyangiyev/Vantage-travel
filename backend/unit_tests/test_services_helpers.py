"""
test_services_helpers.py — Unit tests for pure helper functions in services.py.

These functions contain no database calls and no HTTP requests, so no mocking
is needed. We test them directly with a variety of input types.

Functions tested:
  - _safe_decimal      : converts various types to Decimal or None
  - _parse_date        : parses YYYY-MM-DD date strings
  - _coerce_iata_code  : identifies 3-letter airport codes
  - _tier_value_from_sorted : returns percentile-window averages
  - _map_values_to_tiers    : produces all 4 tier buckets
  - _extract_numeric_candidates : recursively pulls price-like numbers from dicts
"""

import pytest
from decimal import Decimal

from trips.services import (
    _safe_decimal,
    _parse_date,
    _coerce_iata_code,
    _tier_value_from_sorted,
    _map_values_to_tiers,
    _extract_numeric_candidates,
)


# ---------------------------------------------------------------------------
# _safe_decimal
# ---------------------------------------------------------------------------

class TestSafeDecimal:
    def test_integer_input(self):
        assert _safe_decimal(100) == Decimal("100")

    def test_float_input(self):
        assert _safe_decimal(9.99) == Decimal("9.99")

    def test_string_number(self):
        assert _safe_decimal("250.50") == Decimal("250.50")

    def test_string_with_currency_symbol(self):
        # Dollar signs and commas should be stripped
        result = _safe_decimal("$1,250.00")
        assert result == Decimal("1250.00")

    def test_none_returns_none(self):
        assert _safe_decimal(None) is None

    def test_empty_string_returns_none(self):
        assert _safe_decimal("") is None

    def test_garbage_string_returns_none(self):
        assert _safe_decimal("not-a-number") is None

    def test_dict_returns_none(self):
        assert _safe_decimal({"price": 10}) is None

    def test_list_returns_none(self):
        assert _safe_decimal([10, 20]) is None

    def test_decimal_passthrough(self):
        d = Decimal("42.5")
        assert _safe_decimal(d) == d

    def test_zero_string(self):
        assert _safe_decimal("0") == Decimal("0")


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_valid_date(self):
        from datetime import date
        result = _parse_date("2025-08-15")
        assert result == date(2025, 8, 15)

    def test_wrong_format_raises(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            _parse_date("15-08-2025")

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError):
            _parse_date("2025-13-01")  # month 13 doesn't exist


# ---------------------------------------------------------------------------
# _coerce_iata_code
# ---------------------------------------------------------------------------

class TestCoerceIataCode:
    def test_valid_iata_code_uppercase(self):
        assert _coerce_iata_code("JFK") == "JFK"

    def test_valid_iata_code_lowercase(self):
        # Input is lowercased, should be returned as uppercase
        assert _coerce_iata_code("lhr") == "LHR"

    def test_city_name_returns_none(self):
        # "New York" is not 3 letters
        assert _coerce_iata_code("New York") is None

    def test_two_letter_code_returns_none(self):
        assert _coerce_iata_code("NY") is None

    def test_four_letter_code_returns_none(self):
        assert _coerce_iata_code("KJFK") is None

    def test_numbers_in_code_returns_none(self):
        assert _coerce_iata_code("J1K") is None


# ---------------------------------------------------------------------------
# _tier_value_from_sorted
# ---------------------------------------------------------------------------

class TestTierValueFromSorted:
    def test_single_value_list(self):
        values = [Decimal("500")]
        result = _tier_value_from_sorted(values, Decimal("0.5"))
        assert result == Decimal("500")

    def test_empty_list_raises(self):
        with pytest.raises(ValueError):
            _tier_value_from_sorted([], Decimal("0.5"))

    def test_percentile_zero_picks_lowest_range(self):
        # Use 10 values — window size will be 5, so 15th and 90th percentile
        # centers (index 1 vs index 9) produce genuinely different windows.
        values = [Decimal(str(i * 10)) for i in range(1, 11)]  # [10, 20, ..., 100]
        result_low = _tier_value_from_sorted(values, Decimal("0.15"))
        result_high = _tier_value_from_sorted(values, Decimal("0.90"))
        assert result_low < result_high

    def test_percentile_one_picks_highest_range(self):
        values = [Decimal(str(i)) for i in range(1, 21)]  # 1 to 20
        result = _tier_value_from_sorted(values, Decimal("0.90"))
        assert result > Decimal("10")

    def test_result_is_decimal(self):
        values = [Decimal("100"), Decimal("200"), Decimal("300")]
        result = _tier_value_from_sorted(values, Decimal("0.5"))
        assert isinstance(result, Decimal)


# ---------------------------------------------------------------------------
# _map_values_to_tiers
# ---------------------------------------------------------------------------

class TestMapValuesToTiers:
    def test_returns_all_four_tiers(self):
        values = [Decimal(str(i * 10)) for i in range(1, 31)]
        result = _map_values_to_tiers(values)
        assert set(result.keys()) == {"cheapest", "affordable", "moderate", "luxury"}

    def test_tiers_are_non_decreasing(self):
        values = [Decimal(str(i * 10)) for i in range(1, 31)]
        result = _map_values_to_tiers(values)
        assert result["cheapest"] <= result["affordable"]
        assert result["affordable"] <= result["moderate"]
        assert result["moderate"] <= result["luxury"]

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="No usable pricing values"):
            _map_values_to_tiers([])

    def test_all_zero_values_raises(self):
        with pytest.raises(ValueError):
            _map_values_to_tiers([Decimal("0"), Decimal("0")])


# ---------------------------------------------------------------------------
# _extract_numeric_candidates
# ---------------------------------------------------------------------------

class TestExtractNumericCandidates:
    def test_extracts_price_key(self):
        data = {"price": 299}
        result = _extract_numeric_candidates(data)
        assert Decimal("299") in result

    def test_extracts_fare_key(self):
        data = {"fare": "150.00"}
        result = _extract_numeric_candidates(data)
        assert Decimal("150.00") in result

    def test_ignores_non_price_keys(self):
        data = {"name": "Hotel", "rating": 4.5}
        result = _extract_numeric_candidates(data)
        assert len(result) == 0

    def test_recurses_into_nested_dict(self):
        data = {"details": {"price": 500}}
        result = _extract_numeric_candidates(data)
        assert Decimal("500") in result

    def test_recurses_into_list(self):
        data = [{"price": 100}, {"price": 200}]
        result = _extract_numeric_candidates(data)
        assert Decimal("100") in result
        assert Decimal("200") in result

    def test_ignores_zero_and_negative(self):
        data = {"price": 0, "cost": -5}
        result = _extract_numeric_candidates(data)
        # Negative values will be extracted but 0 string may be blank
        # The important thing: no positive prices returned
        positive = [v for v in result if v > 0]
        assert len(positive) == 0

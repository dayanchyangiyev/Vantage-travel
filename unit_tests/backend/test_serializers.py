"""
test_serializers.py — Unit tests for DRF serializers.

Serializers tested:
  - TripSerializer               : validates date ordering, origin_country, pricing_snapshot
  - BudgetTierQuerySerializer    : validates required fields, currency default
  - BudgetEvaluationInputSerializer : validates budget amounts, comfort_preference choices
  - RegisterSerializer           : creates users with hashed passwords
"""

import pytest
from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User

from trips.serializers import (
    TripSerializer,
    BudgetTierQuerySerializer,
    BudgetEvaluationInputSerializer,
)
from accounts.serializers import RegisterSerializer


# ---------------------------------------------------------------------------
# TripSerializer
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTripSerializer:
    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="tester", password="pass123")

    def _valid_data(self):
        return {
            "destination": "Barcelona, Spain",
            "travelers": 2,
            "start_date": date(2025, 8, 1),
            "end_date": date(2025, 8, 10),
            "budget_profile": "affordable",
            "interests": ["beach", "food"],
        }

    def test_valid_data_is_accepted(self, user):
        s = TripSerializer(data=self._valid_data())
        assert s.is_valid(), s.errors

    def test_end_date_before_start_date_rejected(self, user):
        data = self._valid_data()
        data["start_date"] = date(2025, 8, 10)
        data["end_date"] = date(2025, 8, 1)
        s = TripSerializer(data=data)
        assert not s.is_valid()
        assert "end_date" in s.errors

    def test_empty_origin_country_rejected(self, user):
        data = self._valid_data()
        data["origin_country"] = "   "  # whitespace only
        s = TripSerializer(data=data)
        assert not s.is_valid()
        assert "origin_country" in s.errors

    def test_valid_pricing_snapshot_accepted(self, user):
        data = self._valid_data()
        data["pricing_snapshot"] = {
            "tiers": {
                "cheapest": {},
                "affordable": {},
                "moderate": {},
                "luxury": {},
            }
        }
        s = TripSerializer(data=data)
        assert s.is_valid(), s.errors

    def test_pricing_snapshot_missing_tiers_rejected(self, user):
        data = self._valid_data()
        data["pricing_snapshot"] = {"destination_city": "Paris"}  # missing tiers
        s = TripSerializer(data=data)
        assert not s.is_valid()
        assert "pricing_snapshot" in s.errors

    def test_pricing_snapshot_incomplete_tiers_rejected(self, user):
        data = self._valid_data()
        data["pricing_snapshot"] = {
            "tiers": {"cheapest": {}, "affordable": {}}  # missing moderate + luxury
        }
        s = TripSerializer(data=data)
        assert not s.is_valid()
        assert "pricing_snapshot" in s.errors


# ---------------------------------------------------------------------------
# BudgetTierQuerySerializer
# ---------------------------------------------------------------------------

class TestBudgetTierQuerySerializer:
    def _valid_data(self):
        return {
            "origin_city": "New York",
            "destination_city": "Paris",
            "destination_country": "France",
            "departure_date": "2025-09-01",
            "return_date": "2025-09-08",
            "adults": 2,
        }

    def test_valid_data_accepted(self):
        s = BudgetTierQuerySerializer(data=self._valid_data())
        assert s.is_valid(), s.errors

    def test_currency_defaults_to_usd(self):
        data = self._valid_data()  # no currency key
        s = BudgetTierQuerySerializer(data=data)
        s.is_valid()
        assert s.validated_data["currency"] == "USD"

    def test_adults_minimum_is_one(self):
        data = self._valid_data()
        data["adults"] = 0
        s = BudgetTierQuerySerializer(data=data)
        assert not s.is_valid()
        assert "adults" in s.errors

    def test_missing_origin_city_rejected(self):
        data = self._valid_data()
        del data["origin_city"]
        s = BudgetTierQuerySerializer(data=data)
        assert not s.is_valid()
        assert "origin_city" in s.errors


# ---------------------------------------------------------------------------
# BudgetEvaluationInputSerializer
# ---------------------------------------------------------------------------

class TestBudgetEvaluationInputSerializer:
    def _valid_data(self):
        return {
            "origin_city": "New York",
            "destination_city": "Tokyo",
            "destination_country": "Japan",
            "departure_date": "2025-11-01",
            "return_date": "2025-11-14",
            "adults": 1,
            "max_flight_budget": "800.00",
            "total_living_budget": "2500.00",
            "comfort_preference": "moderate",
        }

    def test_valid_data_accepted(self):
        s = BudgetEvaluationInputSerializer(data=self._valid_data())
        assert s.is_valid(), s.errors

    def test_invalid_comfort_preference_rejected(self):
        data = self._valid_data()
        data["comfort_preference"] = "ultra_premium"
        s = BudgetEvaluationInputSerializer(data=data)
        assert not s.is_valid()
        assert "comfort_preference" in s.errors

    def test_all_valid_comfort_tiers_accepted(self):
        for tier in ["cheapest", "affordable", "moderate", "luxury"]:
            data = self._valid_data()
            data["comfort_preference"] = tier
            s = BudgetEvaluationInputSerializer(data=data)
            assert s.is_valid(), f"Tier '{tier}' should be valid but got: {s.errors}"

    def test_negative_flight_budget_rejected(self):
        data = self._valid_data()
        data["max_flight_budget"] = "-100.00"
        s = BudgetEvaluationInputSerializer(data=data)
        assert not s.is_valid()
        assert "max_flight_budget" in s.errors

    def test_negative_living_budget_rejected(self):
        data = self._valid_data()
        data["total_living_budget"] = "-500.00"
        s = BudgetEvaluationInputSerializer(data=data)
        assert not s.is_valid()
        assert "total_living_budget" in s.errors

    def test_zero_budgets_accepted(self):
        """Zero budgets are valid — the evaluation will just mark it infeasible."""
        data = self._valid_data()
        data["max_flight_budget"] = "0.00"
        data["total_living_budget"] = "0.00"
        s = BudgetEvaluationInputSerializer(data=data)
        assert s.is_valid(), s.errors


# ---------------------------------------------------------------------------
# RegisterSerializer (accounts app)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRegisterSerializer:
    def test_creates_user_with_hashed_password(self):
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "strongpassword123",
        }
        s = RegisterSerializer(data=data)
        assert s.is_valid(), s.errors
        user = s.save()

        # Password must be hashed — not stored in plain text
        assert user.password != "strongpassword123"
        assert user.check_password("strongpassword123")

    def test_duplicate_username_rejected(self):
        User.objects.create_user(username="existing", password="pass")
        data = {
            "username": "existing",
            "email": "other@example.com",
            "password": "anotherpass",
        }
        s = RegisterSerializer(data=data)
        assert not s.is_valid()
        assert "username" in s.errors

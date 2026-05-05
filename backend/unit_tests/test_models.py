"""
test_models.py — Unit tests for the Trip Django model.

Tests cover:
  - Happy path: a valid Trip saves without errors
  - clean() validation: end_date before start_date raises ValidationError
  - __str__ output format
  - BudgetProfile choices are what the service layer expects
"""

import pytest
from datetime import date
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from trips.models import Trip


@pytest.mark.django_db
class TestTripModel:
    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="alice", password="pass123")

    def _make_trip(self, user, **overrides):
        """Helper to create a valid Trip with sensible defaults."""
        defaults = dict(
            user=user,
            origin_country="USA",
            destination="Paris, France",
            travelers=2,
            start_date=date(2025, 9, 1),
            end_date=date(2025, 9, 8),
            budget_profile=Trip.BudgetProfile.AFFORDABLE,
        )
        defaults.update(overrides)
        return Trip(**defaults)

    def test_valid_trip_saves(self, user):
        trip = self._make_trip(user)
        trip.full_clean()   # runs model validators
        trip.save()
        assert Trip.objects.filter(user=user).count() == 1

    def test_end_date_before_start_date_raises(self, user):
        trip = self._make_trip(
            user,
            start_date=date(2025, 9, 8),
            end_date=date(2025, 9, 1),   # before start
        )
        with pytest.raises(ValidationError) as exc_info:
            trip.full_clean()
        assert "end_date" in exc_info.value.message_dict

    def test_end_date_equals_start_date_is_valid(self, user):
        """Same-day trips (end == start) should be allowed by the model."""
        trip = self._make_trip(
            user,
            start_date=date(2025, 9, 1),
            end_date=date(2025, 9, 1),
        )
        trip.full_clean()  # should not raise

    def test_str_representation(self, user):
        trip = self._make_trip(user)
        trip.save()
        result = str(trip)
        assert "Paris, France" in result
        assert str(user) in result

    def test_budget_profile_choices(self):
        expected = {"cheapest", "affordable", "moderate", "luxury"}
        actual = {choice[0] for choice in Trip.BudgetProfile.choices}
        assert actual == expected

    def test_default_budget_profile_is_moderate(self, user):
        trip = self._make_trip(user)
        # No budget_profile passed — should default to moderate
        default_trip = Trip(
            user=user,
            destination="Rome",
            travelers=1,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
        )
        assert default_trip.budget_profile == Trip.BudgetProfile.MODERATE

    def test_interests_defaults_to_empty_list(self, user):
        trip = self._make_trip(user)
        trip.save()
        assert trip.interests == []

    def test_engine_output_defaults_to_empty_dict(self, user):
        trip = self._make_trip(user)
        trip.save()
        assert trip.engine_output == {}

    def test_trip_ordering_newest_first(self, user):
        """Trip.Meta.ordering = ['-created_at'] — newest trip should appear first."""
        trip1 = self._make_trip(user, destination="London")
        trip1.save()
        trip2 = self._make_trip(user, destination="Tokyo")
        trip2.save()
        trips = list(Trip.objects.filter(user=user))
        assert trips[0].destination == "Tokyo"  # most recently created

"""
conftest.py — Shared pytest fixtures for all backend unit tests.

The VERY FIRST thing this file does is configure Django. This is required
because pytest-django relies on pytest.ini being discovered from the rootdir,
but when we run tests from the backend/ directory against paths in unit_tests/,
the conftest here is loaded before the ini file takes effect.

All Django model imports are deferred to inside fixtures using inline imports.
"""

import os

# Must happen before any Django import.
# We use test_settings which provides a fixed SECRET_KEY and in-memory SQLite.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.test_settings")

import django  # noqa: E402
django.setup()

# ---- All Django imports go AFTER setup() ----
import pytest  # noqa: E402
from decimal import Decimal  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402
from rest_framework_simplejwt.tokens import RefreshToken  # noqa: E402


# ---------------------------------------------------------------------------
# Django test database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    """A DRF APIClient instance — no authentication by default."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a standard user in the test database."""
    return User.objects.create_user(
        username="traveler",
        email="traveler@example.com",
        password="securepass123",
    )


@pytest.fixture
def auth_client(test_user):
    """An APIClient that carries a valid JWT Bearer token for test_user."""
    client = APIClient()
    refresh = RefreshToken.for_user(test_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


# ---------------------------------------------------------------------------
# Sample API response payloads
# ---------------------------------------------------------------------------

@pytest.fixture
def serpapi_flights_response():
    """Minimal Google Flights response with two price tiers."""
    return {
        "best_flights": [
            {"price": 350, "flights": [{"departure_airport": {"id": "JFK"}}]},
            {"price": 420, "flights": []},
        ],
        "other_flights": [
            {"price": 280},
            {"price": 510},
            {"price": 650},
        ],
    }


@pytest.fixture
def serpapi_hotels_response():
    """Minimal Google Hotels response with rate_per_night structure."""
    return {
        "properties": [
            {"rate_per_night": {"extracted_lowest": 85}},
            {"rate_per_night": {"extracted_lowest": 120}},
            {"rate_per_night": {"extracted_before_taxes_fees": 200}},
            {"extracted_price": 300},
        ],
        "ads": [
            {"extracted_price": 75},
        ],
    }


@pytest.fixture
def google_places_response():
    """Minimal Google Places Text Search response with restaurants."""
    return {
        "places": [
            {"displayName": {"text": "Café Roma"}, "priceLevel": "PRICE_LEVEL_INEXPENSIVE", "rating": 4.2},
            {"displayName": {"text": "Bistro Central"}, "priceLevel": "PRICE_LEVEL_MODERATE", "rating": 4.5},
            {
                "displayName": {"text": "Fine Dining X"},
                "priceLevel": "PRICE_LEVEL_EXPENSIVE",
                "priceRange": {
                    "startPrice": {"units": "40", "nanos": 0},
                    "endPrice": {"units": "80", "nanos": 0},
                },
                "rating": 4.8,
            },
        ]
    }


@pytest.fixture
def serpapi_autocomplete_response():
    """Minimal Google Flights Autocomplete response resolving a city name to an IATA code."""
    return {
        "airports": [
            {
                "id": "JFK",
                "name": "John F. Kennedy International Airport",
            }
        ]
    }

"""
test_views_trips.py — Unit tests for the trips app API endpoints.

Uses Django's APIClient (via conftest fixtures) to hit the actual URL routes.
External API calls (SerpAPI, Google Places) are mocked so tests never touch
the internet.

Endpoints covered:
  GET  /api/trips/                → list/create trips (requires auth)
  POST /api/trips/                → create trip
  GET  /api/trips/current/        → last saved trip
  GET  /api/trips/geonames/       → city autocomplete proxy
  GET  /api/trips/budget/tiers/   → dynamic pricing tiers
  POST /api/trips/budget/evaluate → budget feasibility check
"""

import pytest
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from trips.models import Trip


# ---------------------------------------------------------------------------
# TripListCreateView  — GET /api/trips/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTripListView:
    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/trips/")
        assert response.status_code == 401

    def test_authenticated_returns_200(self, auth_client):
        response = auth_client.get("/api/trips/")
        assert response.status_code == 200

    def test_returns_only_own_trips(self, auth_client, test_user):
        # Create a trip for the test_user
        Trip.objects.create(
            user=test_user,
            destination="Paris",
            travelers=2,
            start_date=date(2025, 9, 1),
            end_date=date(2025, 9, 8),
        )
        # Create a trip for a different user
        other = User.objects.create_user(username="other", password="pass")
        Trip.objects.create(
            user=other,
            destination="Tokyo",
            travelers=1,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 7),
        )

        response = auth_client.get("/api/trips/")
        assert response.status_code == 200
        # Should only see test_user's Paris trip
        destinations = [t["destination"] for t in response.data]
        assert "Paris" in destinations
        assert "Tokyo" not in destinations


# ---------------------------------------------------------------------------
# TripListCreateView  — POST /api/trips/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTripCreateView:
    def test_creates_trip_returns_201(self, auth_client):
        payload = {
            "destination": "Lisbon, Portugal",
            "travelers": 1,
            "start_date": "2025-08-15",
            "end_date": "2025-08-22",
            "budget_profile": "affordable",
        }
        response = auth_client.post("/api/trips/", data=payload, format="json")
        assert response.status_code == 201
        assert response.data["destination"] == "Lisbon, Portugal"

    def test_invalid_dates_returns_400(self, auth_client):
        payload = {
            "destination": "Madrid",
            "travelers": 1,
            "start_date": "2025-08-22",
            "end_date": "2025-08-15",  # before start
            "budget_profile": "moderate",
        }
        response = auth_client.post("/api/trips/", data=payload, format="json")
        assert response.status_code == 400

    def test_unauthenticated_create_returns_401(self, api_client):
        payload = {
            "destination": "Rome",
            "travelers": 2,
            "start_date": "2025-07-01",
            "end_date": "2025-07-10",
        }
        response = api_client.post("/api/trips/", data=payload, format="json")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# CurrentTripView  — GET /api/trips/current/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCurrentTripView:
    def test_returns_404_when_no_trips(self, auth_client):
        response = auth_client.get("/api/trips/current/")
        assert response.status_code == 404

    def test_returns_most_recent_trip(self, auth_client, test_user):
        Trip.objects.create(
            user=test_user,
            destination="Rome",
            travelers=1,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 8),
        )
        Trip.objects.create(
            user=test_user,
            destination="Barcelona",
            travelers=2,
            start_date=date(2025, 8, 1),
            end_date=date(2025, 8, 10),
        )
        response = auth_client.get("/api/trips/current/")
        assert response.status_code == 200
        # Most recently created is Barcelona
        assert response.data["destination"] == "Barcelona"

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/trips/current/")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# geonames_search  — GET /api/trips/geonames/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGeonamesSearchView:
    def test_short_query_returns_empty(self, api_client, settings):
        settings.GEONAMES_USERNAME = "testuser"
        response = api_client.get("/api/trips/geonames/?q=a")
        assert response.status_code == 200
        assert response.data == {"geonames": []}

    def test_no_geonames_username_returns_empty(self, api_client, settings):
        settings.GEONAMES_USERNAME = ""
        response = api_client.get("/api/trips/geonames/?q=paris")
        assert response.status_code == 200
        assert response.data == {"geonames": []}

    def test_proxies_geonames_response(self, api_client, settings, mocker):
        settings.GEONAMES_USERNAME = "testuser"
        fake_geonames = {
            "geonames": [
                {
                    "geonameId": 2968815,
                    "name": "Paris",
                    "countryName": "France",
                    "fcode": "PPLC",
                    "population": 2138551,
                }
            ]
        }
        # Mock the urllib call inside the view
        mock_response = mocker.MagicMock()
        mock_response.read.return_value = str(fake_geonames).replace("'", '"').encode()
        mock_response.getcode.return_value = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = mocker.MagicMock(return_value=False)

        mocker.patch("urllib.request.urlopen", return_value=mock_response)
        # Import json and patch json.loads separately to avoid encoding issues
        import json
        mocker.patch("json.loads", return_value=fake_geonames)

        response = api_client.get("/api/trips/geonames/?q=paris")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# budget_country_tiers  — GET /api/trips/budget/tiers/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBudgetTiersView:
    def _mock_providers(self, mocker):
        tier_data = {
            "cheapest": Decimal("200"),
            "affordable": Decimal("400"),
            "moderate": Decimal("700"),
            "luxury": Decimal("1200"),
        }
        local_data = {
            "cheapest": Decimal("30"),
            "affordable": Decimal("60"),
            "moderate": Decimal("100"),
            "luxury": Decimal("180"),
        }
        mocker.patch("trips.services.SerpApiFlightProvider.fetch_tier_prices", return_value=tier_data)
        mocker.patch("trips.services.SerpApiHotelProvider.fetch_tier_prices", return_value=tier_data)
        mocker.patch("trips.services.LocalCostProvider.fetch_daily_tier_costs", return_value=local_data)

    def test_valid_request_returns_200(self, api_client, mocker):
        self._mock_providers(mocker)
        params = (
            "origin_city=New+York"
            "&destination_city=Paris"
            "&destination_country=France"
            "&departure_date=2025-09-01"
            "&return_date=2025-09-08"
            "&adults=2"
        )
        response = api_client.get(f"/api/trips/budget/tiers/?{params}")
        assert response.status_code == 200
        assert "tiers" in response.data

    def test_missing_required_params_returns_400(self, api_client):
        response = api_client.get("/api/trips/budget/tiers/?origin_city=NYC")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# evaluate_budget  — POST /api/trips/budget/evaluate/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEvaluateBudgetView:
    def _mock_providers(self, mocker):
        tier_data = {
            "cheapest": Decimal("200"),
            "affordable": Decimal("400"),
            "moderate": Decimal("700"),
            "luxury": Decimal("1200"),
        }
        local_data = {
            "cheapest": Decimal("30"),
            "affordable": Decimal("60"),
            "moderate": Decimal("100"),
            "luxury": Decimal("180"),
        }
        mocker.patch("trips.services.SerpApiFlightProvider.fetch_tier_prices", return_value=tier_data)
        mocker.patch("trips.services.SerpApiHotelProvider.fetch_tier_prices", return_value=tier_data)
        mocker.patch("trips.services.LocalCostProvider.fetch_daily_tier_costs", return_value=local_data)

    def test_valid_payload_returns_200(self, api_client, mocker):
        self._mock_providers(mocker)
        payload = {
            "origin_city": "New York",
            "destination_city": "Paris",
            "destination_country": "France",
            "departure_date": "2025-09-01",
            "return_date": "2025-09-08",
            "adults": 1,
            "max_flight_budget": "500.00",
            "total_living_budget": "2000.00",
            "comfort_preference": "affordable",
            "currency": "USD",
        }
        response = api_client.post("/api/trips/budget/evaluate/", data=payload, format="json")
        assert response.status_code == 200
        assert "feasible" in response.data

    def test_invalid_comfort_preference_returns_400(self, api_client):
        payload = {
            "origin_city": "NYC",
            "destination_city": "Paris",
            "destination_country": "France",
            "departure_date": "2025-09-01",
            "return_date": "2025-09-08",
            "adults": 1,
            "max_flight_budget": "500.00",
            "total_living_budget": "2000.00",
            "comfort_preference": "ultra_luxury",  # invalid
        }
        response = api_client.post("/api/trips/budget/evaluate/", data=payload, format="json")
        assert response.status_code == 400

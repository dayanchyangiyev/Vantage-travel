"""
test_views_search.py — Unit tests for the flight/hotel search endpoints and
the trip selection PATCH endpoint. The service layer is mocked so no real
LiteAPI calls are made.
"""

import pytest
from django.urls import reverse


CATEGORIZED_FLIGHTS = {
    "origin": "JFK",
    "destination": "FCO",
    "currency": "USD",
    "tiers": {
        "cheapest": [{"id": "f1", "airline": "TAP", "price": 437.75, "currency": "USD",
                      "stops": 1, "duration_minutes": 540, "departure_time": "", "arrival_time": "",
                      "origin": "JFK", "destination": "FCO", "provider": "FLIGHTHUB"}],
        "affordable": [],
        "moderate": [],
        "luxury": [],
    },
}

CATEGORIZED_HOTELS = {
    "destination_city": "Rome",
    "destination_country": "Italy",
    "currency": "USD",
    "nights": 3,
    "tiers": {"cheapest": [{"id": "h1", "name": "Romoli Hotel", "price": 291.83,
                            "currency": "USD", "nights": 3, "stars": 3, "rating": 8.1,
                            "board_name": "Room Only", "refundable": True,
                            "thumbnail": "a.jpg", "address": "Via A"}],
              "affordable": [], "moderate": [], "luxury": []},
}


class TestFlightSearchView:
    def test_returns_categorized_options(self, api_client, mocker):
        mocker.patch("trips.views.search_flight_options", return_value=CATEGORIZED_FLIGHTS)
        url = reverse("flight-search")
        resp = api_client.get(url, {
            "origin_city": "New York", "destination_city": "Rome",
            "departure_date": "2026-09-10", "return_date": "2026-09-13", "adults": 1,
        })
        assert resp.status_code == 200
        assert resp.data["tiers"]["cheapest"][0]["airline"] == "TAP"

    def test_missing_param_is_400(self, api_client):
        url = reverse("flight-search")
        resp = api_client.get(url, {"origin_city": "New York"})
        assert resp.status_code == 400

    def test_service_value_error_is_400(self, api_client, mocker):
        mocker.patch("trips.views.search_flight_options", side_effect=ValueError("No flight options"))
        url = reverse("flight-search")
        resp = api_client.get(url, {
            "origin_city": "New York", "destination_city": "Rome",
            "departure_date": "2026-09-10", "return_date": "2026-09-13", "adults": 1,
        })
        assert resp.status_code == 400
        assert "No flight options" in resp.data["detail"]


class TestHotelSearchView:
    def test_returns_categorized_options(self, api_client, mocker):
        mocker.patch("trips.views.search_hotel_options", return_value=CATEGORIZED_HOTELS)
        url = reverse("hotel-search")
        resp = api_client.get(url, {
            "destination_city": "Rome", "destination_country": "Italy",
            "check_in": "2026-09-10", "check_out": "2026-09-13", "adults": 2,
        })
        assert resp.status_code == 200
        assert resp.data["tiers"]["cheapest"][0]["name"] == "Romoli Hotel"

    def test_missing_param_is_400(self, api_client):
        url = reverse("hotel-search")
        resp = api_client.get(url, {"destination_city": "Rome"})
        assert resp.status_code == 400


class TestHotelBookingView:
    def test_books_and_returns_confirmation(self, api_client, mocker):
        mocker.patch(
            "trips.views.create_hotel_booking",
            return_value={
                "booking_id": "PyPdNLMVq", "supplier_booking_id": "PyPdNLMVq",
                "status": "CONFIRMED", "hotel_confirmation_code": "test",
                "price": 805.1, "currency": "USD",
            },
        )
        resp = api_client.post(reverse("hotel-booking"), {
            "offer_id": "abc", "first_name": "John", "last_name": "Traveler",
            "email": "john@example.com",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["status"] == "CONFIRMED"
        assert resp.data["booking_id"] == "PyPdNLMVq"

    def test_missing_field_is_400(self, api_client):
        resp = api_client.post(reverse("hotel-booking"), {"offer_id": "abc"}, format="json")
        assert resp.status_code == 400

    def test_expired_offer_is_400(self, api_client, mocker):
        mocker.patch(
            "trips.views.create_hotel_booking",
            side_effect=ValueError("This rate is no longer available to book"),
        )
        resp = api_client.post(reverse("hotel-booking"), {
            "offer_id": "stale", "first_name": "A", "last_name": "B", "email": "a@b.com",
        }, format="json")
        assert resp.status_code == 400
        assert "no longer available" in resp.data["detail"]


class TestNuiteeBookingProvider:
    def test_prebook_then_book_flow(self, mocker):
        from trips.services import NuiteeBookingProvider, HotelBookingInput
        provider = NuiteeBookingProvider()
        post = mocker.patch.object(provider.client, "post", side_effect=[
            {"data": {"prebookId": "pb1", "price": 805.1, "currency": "USD"}},
            {"data": {"bookingId": "bk1", "supplierBookingId": "bk1",
                      "status": "CONFIRMED", "hotelConfirmationCode": "test"}},
        ])
        result = provider.book_hotel(HotelBookingInput("offer1", "John", "Doe", "j@d.com"))
        assert result["booking_id"] == "bk1"
        assert result["status"] == "CONFIRMED"
        assert result["price"] == 805.1
        # prebook called first, then book
        assert post.call_args_list[0].args[0] == "rates/prebook"
        assert post.call_args_list[1].args[0] == "rates/book"

    def test_raises_when_prebook_has_no_id(self, mocker):
        from trips.services import NuiteeBookingProvider, HotelBookingInput
        provider = NuiteeBookingProvider()
        mocker.patch.object(provider.client, "post", return_value={"data": {}})
        with pytest.raises(ValueError, match="no longer available"):
            provider.book_hotel(HotelBookingInput("offer1", "John", "Doe", "j@d.com"))


class TestTripSelectionPatch:
    def _make_trip(self, user):
        from trips.models import Trip
        return Trip.objects.create(
            user=user, origin_country="New York", destination="Rome, Italy",
            travelers=2, start_date="2026-09-10", end_date="2026-09-13",
            budget_profile="moderate", interests=[],
        )

    def test_patch_saves_selection(self, auth_client, test_user):
        trip = self._make_trip(test_user)
        url = reverse("trip-detail", args=[trip.id])
        flight = {"id": "f1", "airline": "TAP", "price": 437.75}
        hotel = {"id": "h1", "name": "Romoli Hotel", "price": 291.83}

        resp = auth_client.patch(url, {"selected_flight": flight, "selected_hotel": hotel}, format="json")
        assert resp.status_code == 200

        trip.refresh_from_db()
        assert trip.selected_flight["airline"] == "TAP"
        assert trip.selected_hotel["name"] == "Romoli Hotel"

    def test_patch_requires_auth(self, api_client, test_user):
        trip = self._make_trip(test_user)
        url = reverse("trip-detail", args=[trip.id])
        resp = api_client.patch(url, {"selected_flight": {}}, format="json")
        assert resp.status_code in (401, 403)

    def test_cannot_patch_another_users_trip(self, auth_client, test_user, django_user_model):
        other = django_user_model.objects.create_user(username="other", password="x")
        trip = self._make_trip(other)
        url = reverse("trip-detail", args=[trip.id])
        resp = auth_client.patch(url, {"selected_flight": {"id": "x"}}, format="json")
        assert resp.status_code == 404

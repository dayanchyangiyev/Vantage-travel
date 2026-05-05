import pytest
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

class TestDestinationWeatherView:
    def test_missing_required_params_returns_400(self, api_client):
        response = api_client.get("/api/trips/weather/")
        assert response.status_code == 400
        assert "destination_city" in response.data
        assert "destination_country" in response.data

    def test_valid_request_returns_200(self, api_client, mocker):
        mock_fetch = mocker.patch("trips.views.fetch_destination_weather")
        mock_fetch.return_value = {
            "condition": "Sunny",
            "high_c": 25.0,
            "low_c": 15.0,
            "high_f": 77.0,
            "low_f": 59.0,
            "humidity_pct": 50,
            "precipitation_pct": 10,
            "date_label": "Current 10-day forecast",
            "is_forecast": False
        }

        response = api_client.get(
            "/api/trips/weather/?destination_city=Paris&destination_country=France"
        )
        
        assert response.status_code == 200
        assert response.data["condition"] == "Sunny"
        assert response.data["high_c"] == 25.0
        mock_fetch.assert_called_once_with(
            destination_city="Paris", 
            destination_country="France", 
            start_date=None, 
            end_date=None
        )

    def test_handles_service_exception(self, api_client, mocker):
        mock_fetch = mocker.patch("trips.views.fetch_destination_weather")
        mock_fetch.side_effect = RuntimeError("Something unexpected")

        response = api_client.get(
            "/api/trips/weather/?destination_city=Paris&destination_country=France"
        )
        
        assert response.status_code == 503
        assert "Weather service temporarily unavailable" in response.data["detail"]

from datetime import date, timedelta
from decimal import Decimal
import pytest

from django.conf import settings

from trips.services import GoogleWeatherProvider, fetch_destination_weather

class TestGoogleWeatherProvider:
    @pytest.fixture
    def mock_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_WEATHER_API_KEY", "test_weather_key")
        monkeypatch.setattr(settings, "GEONAMES_USERNAME", "test_geonames_user")
        monkeypatch.setattr(
            settings,
            "GOOGLE_WEATHER_BASE_URL",
            "https://weather.googleapis.com/v1/forecast/days:lookup",
        )

    @pytest.fixture
    def mock_http_json(self, mocker):
        return mocker.patch("trips.services._http_request_json")

    def test_geocode_success(self, mock_settings, mock_http_json):
        mock_http_json.return_value = {
            "geonames": [{"lat": "48.8566", "lng": "2.3522"}]
        }
        provider = GoogleWeatherProvider()
        lat, lng = provider._geocode("Paris", "France")
        
        assert lat == 48.8566
        assert lng == 2.3522
        mock_http_json.assert_called_once()
        args, kwargs = mock_http_json.call_args
        assert kwargs["params"]["q"] == "Paris, France"
        assert kwargs["params"]["username"] == "test_geonames_user"

    def test_geocode_no_results(self, mock_settings, mock_http_json):
        mock_http_json.return_value = {"geonames": []}
        provider = GoogleWeatherProvider()
        
        with pytest.raises(ValueError, match="Cannot geocode 'Nowhere, NullIsland'"):
            provider._geocode("Nowhere", "NullIsland")

    def test_fetch_summary_no_api_key(self, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_WEATHER_API_KEY", "")
        provider = GoogleWeatherProvider()
        
        with pytest.raises(ValueError, match="GOOGLE_WEATHER_API_KEY is missing"):
            provider.fetch_summary("Paris", "France")

    def test_fetch_summary_success_current_forecast(self, mock_settings, mock_http_json, mocker):
        # Mock geocode to bypass HTTP call
        mocker.patch.object(GoogleWeatherProvider, "_geocode", return_value=(48.8566, 2.3522))
        
        mock_http_json.return_value = {
            "forecastDays": [
                {
                    "maxTemperature": {"degrees": 25.5},
                    "minTemperature": {"degrees": 15.0},
                    "daytimeForecast": {
                        "relativeHumidity": 60,
                        "precipitation": {"probability": {"percent": 10}},
                        "weatherCondition": {"description": {"text": "Sunny"}}
                    }
                },
                {
                    "maxTemperature": {"degrees": 20.0},
                    "minTemperature": {"degrees": 12.0},
                    "daytimeForecast": {
                        "relativeHumidity": 80,
                        "precipitation": {"probability": {"percent": 90}},
                        "weatherCondition": {"description": {"text": "Rainy"}}
                    }
                }
            ]
        }
        
        provider = GoogleWeatherProvider()
        result = provider.fetch_summary("Paris", "France")
        
        assert result["condition"] == "Rainy" or result["condition"] == "Sunny"
        assert result["high_c"] == 22.8
        assert result["low_c"] == 13.5
        assert result["humidity_pct"] == 70
        assert result["precipitation_pct"] == 50
        assert result["date_label"] == "Current 10-day forecast"
        assert result["is_forecast"] is False

    def test_fetch_summary_trip_within_10_days(self, mock_settings, mock_http_json, mocker):
        mocker.patch.object(GoogleWeatherProvider, "_geocode", return_value=(48.8566, 2.3522))
        
        today = date.today()
        trip_start = today + timedelta(days=2)
        trip_end = today + timedelta(days=4)
        
        mock_http_json.return_value = {
            "forecastDays": [
                {
                    "year": trip_start.year,
                    "month": trip_start.month,
                    "day": trip_start.day,
                    "displayDate": {
                        "year": trip_start.year,
                        "month": trip_start.month,
                        "day": trip_start.day,
                    },
                    "maxTemperature": {"degrees": 30.0},
                    "minTemperature": {"degrees": 20.0},
                    "daytimeForecast": {
                        "relativeHumidity": 50,
                        "precipitation": {"probability": {"percent": 0}},
                        "weatherCondition": {"description": {"text": "Clear"}}
                    }
                }
            ]
        }
        
        provider = GoogleWeatherProvider()
        result = provider.fetch_summary(
            "Paris", 
            "France", 
            start_date=trip_start.isoformat(), 
            end_date=trip_end.isoformat()
        )
        
        assert "Forecast for your trip" in result["date_label"]
        assert result["is_forecast"] is True
        assert result["high_c"] == 30.0
        assert result["condition"] == "Clear"

    def test_fetch_destination_weather_helper(self, mocker):
        mock_summary = mocker.patch.object(GoogleWeatherProvider, "fetch_summary", return_value={"mock": "data"})
        
        res = fetch_destination_weather("Paris", "France", "2026-05-10", "2026-05-15")
        
        assert res == {"mock": "data"}
        mock_summary.assert_called_once_with("Paris", "France", "2026-05-10", "2026-05-15")

"""
test_services_nuitee.py — Unit tests for the LiteAPI (Nuitee Connect) flight
and hotel option providers.

All HTTP is mocked: LiteApiClient.post / LiteApiClient.get are patched so the
real LiteAPI sandbox is never contacted. Fixtures mirror the verified sandbox
response shapes.
"""

import pytest

from trips.services import (
    FlightSearchInput,
    HotelSearchInput,
    NuiteeFlightProvider,
    NuiteeHotelProvider,
    TIER_ORDER,
    _bucket_options_by_price,
    search_flight_options,
    search_hotel_options,
)


# ---------------------------------------------------------------------------
# _bucket_options_by_price — quantile split into the four tiers
# ---------------------------------------------------------------------------

class TestBucketOptionsByPrice:
    def test_splits_into_four_tiers_ascending(self):
        options = [{"price": p} for p in (100, 200, 300, 400, 500, 600, 700, 800)]
        buckets = _bucket_options_by_price(options, per_tier=3)

        assert set(buckets.keys()) == set(TIER_ORDER)
        # Cheapest band holds the lowest prices, luxury the highest.
        assert buckets["cheapest"][0]["price"] == 100
        assert max(o["price"] for o in buckets["luxury"]) == 800
        cheapest_max = max(o["price"] for o in buckets["cheapest"])
        luxury_min = min(o["price"] for o in buckets["luxury"])
        assert cheapest_max < luxury_min

    def test_caps_per_tier(self):
        options = [{"price": p} for p in range(1, 41)]  # 40 options
        buckets = _bucket_options_by_price(options, per_tier=3)
        for tier in TIER_ORDER:
            assert len(buckets[tier]) <= 3
            assert len(buckets[tier]) >= 1

    def test_ignores_non_positive_prices(self):
        options = [{"price": 0}, {"price": -5}, {"price": None}, {"price": 100}]
        buckets = _bucket_options_by_price(options)
        flat = [o for tier in TIER_ORDER for o in buckets[tier]]
        assert len(flat) == 1
        assert flat[0]["price"] == 100

    def test_empty_input_returns_empty_tiers(self):
        buckets = _bucket_options_by_price([])
        assert buckets == {tier: [] for tier in TIER_ORDER}


# ---------------------------------------------------------------------------
# Fixtures — sandbox-shaped payloads
# ---------------------------------------------------------------------------

def _journey(total, airline, dep, arr, stops=1, currency="USD"):
    """Build a minimal LiteAPI flight journey with `stops` outbound segments."""
    segments = []
    for i in range(stops + 1):
        segments.append(
            {
                "direction": "OUTBOUND",
                "carrier": {"marketingName": airline},
                "originCode": "JFK" if i == 0 else "XXX",
                "destinationCode": "FCO" if i == stops else "XXX",
                "departureTime": dep,
                "arrivalTime": arr,
                "duration": {"minutes": 200},
                "flight": {"marketingNumber": "100"},
            }
        )
    return {
        "journeyKey": f"{airline}-{total}-{dep}",
        "totalDuration": {"minutes": 540},
        "segments": segments,
        "cheapestOffer": {
            "offerId": f"offer-{airline}-{total}-{dep}",
            "pricing": {"display": {"total": total, "currency": currency}},
            "provider": {"code": "FLIGHTHUB"},
        },
    }


@pytest.fixture
def flights_rates_payload():
    journeys = [
        _journey(437.75, "TAP", "2026-09-10T23:00:00", "2026-09-11T12:00:00"),
        _journey(531.95, "United", "2026-09-10T16:30:00", "2026-09-11T08:00:00"),
        _journey(554.82, "Delta", "2026-09-10T16:40:00", "2026-09-11T09:00:00"),
        _journey(661.90, "Aer Lingus", "2026-09-10T17:35:00", "2026-09-11T10:00:00"),
        # Exact duplicate of TAP offer — must be collapsed.
        _journey(437.75, "TAP", "2026-09-10T23:00:00", "2026-09-11T12:00:00"),
        _journey(0, "Broken", "2026-09-10T01:00:00", "2026-09-11T02:00:00"),  # dropped
    ]
    return {"data": [{"journeys": journeys}]}


@pytest.fixture
def hotels_rates_payload():
    def hotel(hid, amount):
        return {
            "hotelId": hid,
            "roomTypes": [
                {
                    "offerId": f"{hid}-offer",
                    "offerRetailRate": {"amount": amount, "currency": "USD"},
                    "rates": [
                        {
                            "boardName": "Room Only",
                            "cancellationPolicies": {"refundableTag": "RFN"},
                            "retailRate": {"total": [{"amount": amount, "currency": "USD"}]},
                        }
                    ],
                }
            ],
        }

    return {
        "data": [
            hotel("lp1", 291.83),
            hotel("lp2", 565.97),
            hotel("lp3", 827.01),
            hotel("lp4", 1278.57),
        ]
    }


@pytest.fixture
def hotels_directory_payload():
    return {
        "data": [
            {"id": "lp1", "name": "Romoli Hotel", "stars": 3, "rating": 8.1, "main_photo": "a.jpg", "address": "Via A"},
            {"id": "lp2", "name": "Shangri-La Roma", "stars": 4, "rating": 8.6, "main_photo": "b.jpg", "address": "Via B"},
            {"id": "lp3", "name": "Starhotels", "stars": 4, "rating": 8.8, "main_photo": "c.jpg", "address": "Via C"},
            {"id": "lp4", "name": "Tree Charme", "stars": 5, "rating": 9.1, "main_photo": "d.jpg", "address": "Via D"},
        ]
    }


# ---------------------------------------------------------------------------
# NuiteeFlightProvider
# ---------------------------------------------------------------------------

class TestNuiteeFlightProvider:
    def test_search_options_one_way(self, flights_rates_payload, mocker):
        """No return date → a single leg search with one-way prices."""
        provider = NuiteeFlightProvider()
        mocker.patch.object(provider, "_resolve_airport", side_effect=["JFK", "FCO"])
        post = mocker.patch.object(provider.client, "post", return_value=flights_rates_payload)

        result = provider.search_options(
            FlightSearchInput("New York", "Rome", "2026-09-10", "", 1, "USD")
        )

        assert post.call_count == 1  # only the outbound leg is searched
        assert result["origin"] == "JFK"
        assert result["destination"] == "FCO"
        flat = [o for tier in TIER_ORDER for o in result["tiers"][tier]]
        assert len(flat) == 4
        sample = result["tiers"]["cheapest"][0]
        assert sample["airline"] == "TAP"
        assert sample["price"] == 437.75
        assert sample["stops"] == 1
        assert sample["origin"] == "JFK"
        assert sample.get("round_trip") is not True

    def test_search_options_round_trip_combines_legs(self, flights_rates_payload, mocker):
        """A return date → two leg searches combined into round trips (summed price)."""
        provider = NuiteeFlightProvider()
        mocker.patch.object(provider, "_resolve_airport", side_effect=["JFK", "FCO"])
        post = mocker.patch.object(provider.client, "post", return_value=flights_rates_payload)

        result = provider.search_options(
            FlightSearchInput("New York", "Rome", "2026-09-10", "2026-09-13", 1, "USD")
        )

        assert post.call_count == 2  # outbound + return legs
        assert set(result["tiers"].keys()) == set(TIER_ORDER)
        sample = result["tiers"]["cheapest"][0]
        assert sample["round_trip"] is True
        # Same mocked payload for both legs → combined price is double the one-way.
        assert sample["price"] == 875.5
        assert sample["outbound_price"] == 437.75
        assert sample["return_price"] == 437.75
        assert sample["return_airline"] == "TAP"
        assert "|" in sample["id"]  # combined outbound|return offer id

    def test_search_options_raises_when_no_journeys(self, mocker):
        provider = NuiteeFlightProvider()
        mocker.patch.object(provider, "_resolve_airport", side_effect=["JFK", "FCO"])
        mocker.patch.object(provider.client, "post", return_value={"data": []})

        with pytest.raises(ValueError, match="No flight options"):
            provider.search_options(
                FlightSearchInput("NYC", "Rome", "2026-09-10", "2026-09-13", 1, "USD")
            )

    def test_resolve_airport_prefers_metro_then_serviceable(self, mocker):
        provider = NuiteeFlightProvider()
        airports_payload = {
            "data": [
                {
                    "airports": [
                        {"iata": "ROM", "name": "Rome - All Airports", "hasAirlineService": False},
                        {"iata": "CIA", "name": "Ciampino", "hasAirlineService": True},
                        {"iata": "FCO", "name": "Fiumicino", "hasAirlineService": True},
                    ]
                }
            ]
        }
        mocker.patch.object(provider.client, "get", return_value=airports_payload)
        assert provider._resolve_airport("Rome") == "ROM"

    def test_resolve_airport_passthrough_for_iata(self):
        provider = NuiteeFlightProvider()
        assert provider._resolve_airport("JFK") == "JFK"


# ---------------------------------------------------------------------------
# NuiteeHotelProvider
# ---------------------------------------------------------------------------

class TestNuiteeHotelProvider:
    def test_search_options_buckets_and_joins_names(
        self, hotels_rates_payload, hotels_directory_payload, mocker
    ):
        provider = NuiteeHotelProvider()
        mocker.patch.object(provider.client, "post", return_value=hotels_rates_payload)
        mocker.patch.object(provider.client, "get", return_value=hotels_directory_payload)

        result = provider.search_options(
            HotelSearchInput("Rome", "Italy", "2026-09-10", "2026-09-13", 2, "USD")
        )

        assert result["nights"] == 3
        assert set(result["tiers"].keys()) == set(TIER_ORDER)
        cheapest = result["tiers"]["cheapest"][0]
        assert cheapest["name"] == "Romoli Hotel"
        assert cheapest["price"] == 291.83
        assert cheapest["stars"] == 3
        assert cheapest["refundable"] is True
        luxury = result["tiers"]["luxury"][0]
        assert luxury["name"] == "Tree Charme"

    def test_search_options_works_without_directory(self, hotels_rates_payload, mocker):
        """If the name lookup fails, options still return with fallback names."""
        provider = NuiteeHotelProvider()
        mocker.patch.object(provider.client, "post", return_value=hotels_rates_payload)
        mocker.patch.object(provider.client, "get", side_effect=Exception("boom"))

        result = provider.search_options(
            HotelSearchInput("Rome", "Italy", "2026-09-10", "2026-09-13", 2, "USD")
        )
        cheapest = result["tiers"]["cheapest"][0]
        assert cheapest["name"].startswith("Hotel ")

    def test_search_options_raises_when_no_hotels(self, mocker):
        provider = NuiteeHotelProvider()
        mocker.patch.object(provider.client, "post", return_value={"data": []})

        with pytest.raises(ValueError, match="No hotel options"):
            provider.search_options(
                HotelSearchInput("Nowhere", "Void", "2026-09-10", "2026-09-13", 2, "USD")
            )


# ---------------------------------------------------------------------------
# Service entry points — input guards
# ---------------------------------------------------------------------------

class TestServiceEntryPoints:
    def test_flight_search_rejects_zero_adults(self):
        with pytest.raises(ValueError, match="adults"):
            search_flight_options(
                FlightSearchInput("NYC", "Rome", "2026-09-10", "2026-09-13", 0, "USD")
            )

    def test_hotel_search_rejects_zero_adults(self):
        with pytest.raises(ValueError, match="adults"):
            search_hotel_options(
                HotelSearchInput("Rome", "Italy", "2026-09-10", "2026-09-13", 0, "USD")
            )

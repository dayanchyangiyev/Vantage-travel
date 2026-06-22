from django.urls import path

from .views import (
    CurrentTripView,
    TripDetailView,
    TripListCreateView,
    budget_country_tiers,
    destination_weather,
    evaluate_budget,
    flight_search,
    geonames_search,
    hotel_search,
)

urlpatterns = [
    path("", TripListCreateView.as_view(), name="trip-list-create"),
    path("current/", CurrentTripView.as_view(), name="trip-current"),
    path("geonames/", geonames_search, name="geonames-search"),
    path("budget/tiers/", budget_country_tiers, name="budget-country-tiers"),
    path("budget/evaluate/", evaluate_budget, name="budget-evaluate"),
    path("weather/", destination_weather, name="destination-weather"),
    path("flights/search/", flight_search, name="flight-search"),
    path("hotels/search/", hotel_search, name="hotel-search"),
    path("<int:pk>/", TripDetailView.as_view(), name="trip-detail"),
]

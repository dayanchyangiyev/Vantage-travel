from django.urls import path

from .views import (
    CurrentTripView,
    TripListCreateView,
    budget_country_tiers,
    evaluate_budget,
    geonames_search,
)

urlpatterns = [
    path("", TripListCreateView.as_view(), name="trip-list-create"),
    path("current/", CurrentTripView.as_view(), name="trip-current"),
    path("geonames/", geonames_search, name="geonames-search"),
    path("budget/tiers/", budget_country_tiers, name="budget-country-tiers"),
    path("budget/evaluate/", evaluate_budget, name="budget-evaluate"),
]

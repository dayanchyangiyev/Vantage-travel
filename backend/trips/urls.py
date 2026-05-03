from django.urls import path

from .views import CurrentTripView, TripListCreateView, geonames_search

urlpatterns = [
    path("", TripListCreateView.as_view(), name="trip-list-create"),
    path("current/", CurrentTripView.as_view(), name="trip-current"),
    path("geonames/", geonames_search, name="geonames-search"),
]

from django.urls import path

from .views import CurrentTripView, TripListCreateView

urlpatterns = [
    path("", TripListCreateView.as_view(), name="trip-list-create"),
    path("current/", CurrentTripView.as_view(), name="trip-current"),
]

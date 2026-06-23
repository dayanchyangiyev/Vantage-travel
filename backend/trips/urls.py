from django.urls import path

from .views import (
    ChatSessionDetailView,
    ChatSessionListCreateView,
    CurrentTripView,
    TripDetailView,
    TripListCreateView,
    budget_country_tiers,
    chat_end_session,
    chat_send_message,
    destination_weather,
    evaluate_budget,
    flight_search,
    geonames_search,
    hotel_booking,
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
    path("bookings/", hotel_booking, name="hotel-booking"),
    path("chat/sessions/", ChatSessionListCreateView.as_view(), name="chat-session-list"),
    path("chat/sessions/<int:pk>/", ChatSessionDetailView.as_view(), name="chat-session-detail"),
    path("chat/sessions/<int:pk>/messages/", chat_send_message, name="chat-send-message"),
    path("chat/sessions/<int:pk>/end/", chat_end_session, name="chat-end-session"),
    path("<int:pk>/", TripDetailView.as_view(), name="trip-detail"),
]

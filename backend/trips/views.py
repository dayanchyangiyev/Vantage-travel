from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated

from .models import Trip
from .serializers import TripSerializer


class TripListCreateView(generics.ListCreateAPIView):
    serializer_class = TripSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Trip.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CurrentTripView(generics.RetrieveAPIView):
    serializer_class = TripSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        trip = (
            Trip.objects.filter(user=self.request.user)
            .order_by("-created_at")
            .first()
        )
        if trip is None:
            raise NotFound("No saved trip found for this user.")
        return trip

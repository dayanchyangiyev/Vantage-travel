import json
import urllib.parse
import urllib.request

from django.conf import settings
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Trip
from .serializers import TripSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def geonames_search(request):
    query = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'destination')

    if len(query) < 2:
        return Response({'geonames': []})

    params = {
        'q': query,
        'maxRows': '8',
        'username': settings.GEONAMES_USERNAME,
        'lang': 'en',
        'style': 'MEDIUM',
    }

    if search_type == 'country':
        params['featureCode'] = 'PCLI'
        params['orderby'] = 'relevance'
    else:
        params['featureClass'] = 'P'
        params['orderby'] = 'population'

    url = 'https://secure.geonames.org/searchJSON?' + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return Response(data)
    except Exception:
        return Response({'geonames': []})


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

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


def _filter_destination_results(geonames):
    """
    Keep search results useful without forcing a hardcoded fallback list.
    - Prefer capitals/admin cities (PPLC/PPLA/PPLA2)
    - Include cities (PPL) above a minimum population
    - Dedupe by geonameId
    """
    min_population = 30000
    kept = []
    seen = set()

    for place in geonames:
        geoname_id = place.get("geonameId")
        if geoname_id in seen:
            continue

        code = place.get("fcode")
        population = int(place.get("population") or 0)
        is_admin_city = code in {"PPLC", "PPLA", "PPLA2"}
        is_populated_city = code == "PPL" and population >= min_population

        if is_admin_city or is_populated_city:
            kept.append(place)
            seen.add(geoname_id)

        if len(kept) >= 8:
            break

    return kept


@api_view(['GET'])
@permission_classes([AllowAny])
def geonames_search(request):
    query = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'destination')

    if len(query) < 2 or not settings.GEONAMES_USERNAME:
        return Response({'geonames': []})

    params = {
        'q': query,
        'maxRows': '50',
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

        # Filter destination results to practical city choices without hardcoded fallbacks.
        if search_type != 'country':
            filtered = _filter_destination_results(data.get('geonames', []))
            data['geonames'] = filtered if filtered else data.get('geonames', [])[:8]

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

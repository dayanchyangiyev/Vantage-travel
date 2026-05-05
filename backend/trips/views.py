import json
import time
import urllib.parse
import urllib.request

from django.conf import settings
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Trip
from .serializers import (
    BudgetEvaluationInputSerializer,
    BudgetTierQuerySerializer,
    TripSerializer,
)
from .services import DynamicPricingInput, build_dynamic_tier_quotes, evaluate_dynamic_budget
from .api_logging import log_api_response


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
        started = time.monotonic()
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            duration_ms = int((time.monotonic() - started) * 1000)
            log_api_response(
                provider="secure.geonames.org:searchJSON",
                method="GET",
                url=url,
                request_params=params,
                status_code=resp.getcode(),
                response_body=data,
                duration_ms=duration_ms,
            )

        # Filter destination results to practical city choices without hardcoded fallbacks.
        if search_type != 'country':
            filtered = _filter_destination_results(data.get('geonames', []))
            data['geonames'] = filtered if filtered else data.get('geonames', [])[:8]

        return Response(data)
    except Exception as exc:
        log_api_response(
            provider="secure.geonames.org:searchJSON",
            method="GET",
            url=url,
            request_params=params,
            status_code=None,
            response_body=None,
            error=str(exc),
        )
        return Response({'geonames': []})


@api_view(["GET"])
@permission_classes([AllowAny])
def budget_country_tiers(request):
    serializer = BudgetTierQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data
    pricing_input = DynamicPricingInput(
        origin_city=payload["origin_city"],
        destination_city=payload["destination_city"],
        destination_country=payload["destination_country"],
        departure_date=payload["departure_date"].isoformat(),
        return_date=payload["return_date"].isoformat(),
        adults=payload["adults"],
        max_flight_budget=0,
        total_living_budget=0,
        comfort_preference="affordable",
        currency=payload["currency"],
    )
    try:
        result = build_dynamic_tier_quotes(pricing_input)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def evaluate_budget(request):
    serializer = BudgetEvaluationInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data

    budget_input = DynamicPricingInput(
        origin_city=payload["origin_city"],
        destination_city=payload["destination_city"],
        destination_country=payload["destination_country"],
        departure_date=payload["departure_date"].isoformat(),
        return_date=payload["return_date"].isoformat(),
        adults=payload["adults"],
        max_flight_budget=payload["max_flight_budget"],
        total_living_budget=payload["total_living_budget"],
        comfort_preference=payload["comfort_preference"],
        currency=payload["currency"],
    )

    try:
        result = evaluate_dynamic_budget(budget_input)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(result, status=status.HTTP_200_OK)


class TripListCreateView(generics.ListCreateAPIView):
    serializer_class = TripSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Trip.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CurrentTripView(generics.RetrieveAPIView):
    serializer_class = TripSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        trip = (
            Trip.objects.filter(user=self.request.user)
            .first()
        )
        if trip is None:
            raise NotFound("No saved trip found for this user.")
        return trip

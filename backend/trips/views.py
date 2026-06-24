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

from django.utils import timezone

from .agent import AgentError, run_agent_turn, summarize_session
from .booking import Holder, book_offer
from .models import Booking, ChatSession, SupportOperation, SupportSession, Trip
from .serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    BudgetEvaluationInputSerializer,
    BudgetTierQuerySerializer,
    ChatSessionListSerializer,
    ChatSessionSerializer,
    FlightSearchQuerySerializer,
    HotelSearchQuerySerializer,
    SupportOperationSerializer,
    SupportSessionListSerializer,
    SupportSessionSerializer,
    TripSerializer,
    WeatherQuerySerializer,
)
from .support_agent import SupportAgentError, run_support_turn
from .support_ops import decline_operation, execute_operation
from .services import (
    DynamicPricingInput,
    FlightSearchInput,
    HotelSearchInput,
    build_dynamic_tier_quotes,
    evaluate_dynamic_budget,
    fetch_destination_weather,
    search_flight_options,
    search_hotel_options,
)
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


@api_view(["GET"])
@permission_classes([AllowAny])
def destination_weather(request):
    serializer = WeatherQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data
    start = payload.get("start_date")
    end = payload.get("end_date")
    try:
        result = fetch_destination_weather(
            destination_city=payload["destination_city"],
            destination_country=payload["destination_country"],
            start_date=start.isoformat() if start else None,
            end_date=end.isoformat() if end else None,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        return Response(
            {"detail": "Weather service temporarily unavailable."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(result, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def flight_search(request):
    serializer = FlightSearchQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data
    search_input = FlightSearchInput(
        origin_city=payload["origin_city"],
        destination_city=payload["destination_city"],
        departure_date=payload["departure_date"].isoformat(),
        return_date=payload["return_date"].isoformat(),
        adults=payload["adults"],
        currency=payload["currency"],
    )
    try:
        result = search_flight_options(search_input)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def hotel_search(request):
    serializer = HotelSearchQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data
    search_input = HotelSearchInput(
        destination_city=payload["destination_city"],
        destination_country=payload["destination_country"],
        check_in=payload["check_in"].isoformat(),
        check_out=payload["check_out"].isoformat(),
        adults=payload["adults"],
        currency=payload["currency"],
    )
    try:
        result = search_hotel_options(search_input)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def hotel_booking(request):
    """List the signed-in user's bookings (GET) or create one (POST).

    Booking requires authentication — there is no anonymous booking. Bookings
    are persisted per user and idempotent (the same offer is never booked twice).
    """
    if request.method == "GET":
        bookings = Booking.objects.filter(user=request.user)
        return Response(BookingSerializer(bookings, many=True).data)

    serializer = BookingCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data

    try:
        booking, created = book_offer(
            request.user,
            kind=payload["kind"],
            offer_id=payload["offer_id"],
            holder=Holder(payload["first_name"], payload["last_name"], payload["email"]),
            title=payload["title"],
            price=payload["price"],
            currency=payload["currency"],
            airline=payload["airline"],
            trip=Trip.objects.filter(user=request.user).first(),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        return Response(
            {"detail": "Booking service is temporarily unavailable."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    body = BookingSerializer(booking).data
    body["already_booked"] = not created
    return Response(body, status=status.HTTP_201_CREATED)


class TripListCreateView(generics.ListCreateAPIView):
    serializer_class = TripSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Trip.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TripDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a single trip — used to PATCH the chosen flight/hotel."""

    serializer_class = TripSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Trip.objects.filter(user=self.request.user)


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


# ---------------------------------------------------------------------------
# AI concierge chat — sessions, messages, summaries (Codex agent)
# ---------------------------------------------------------------------------
class ChatSessionListCreateView(generics.ListCreateAPIView):
    """List the user's chat sessions, or start a new one."""

    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        # The list view stays light; creating returns the full session.
        return ChatSessionListSerializer if self.request.method == "GET" else ChatSessionSerializer

    def create(self, request, *args, **kwargs):
        context = request.data.get("context") or {}
        if not isinstance(context, dict):
            context = {}
        title = (request.data.get("title") or "").strip() or "New conversation"
        session = ChatSession.objects.create(
            user=request.user,
            title=title[:160],
            context_snapshot=context,
        )
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChatSessionDetailView(generics.RetrieveAPIView):
    """Retrieve one session with its full transcript (used to resume)."""

    serializer_class = ChatSessionSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)


def _get_owned_session(request, pk):
    try:
        return ChatSession.objects.get(pk=pk, user=request.user)
    except ChatSession.DoesNotExist:
        raise NotFound("Chat session not found.")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_send_message(request, pk):
    """Send a user message; run the Codex agent; return the updated session."""
    session = _get_owned_session(request, pk)
    content = (request.data.get("content") or "").strip()
    if not content:
        return Response({"detail": "Message content is required."},
                        status=status.HTTP_400_BAD_REQUEST)

    # Optionally refresh the trip-context snapshot the agent reads.
    new_context = request.data.get("context")
    if isinstance(new_context, dict) and new_context:
        session.context_snapshot = new_context

    # Run the agent against prior history *before* persisting this turn so the
    # new message is not double-counted in the transcript.
    try:
        reply_text, results = run_agent_turn(session, content)
    except AgentError as exc:
        return Response({"detail": str(exc)},
                        status=status.HTTP_502_BAD_GATEWAY)

    # Name the conversation after its first user message so the history list reads well.
    is_first_message = not session.messages.exists()
    if is_first_message and session.title == "New conversation":
        session.title = (content[:57] + "…") if len(content) > 58 else content

    session.messages.create(role="user", content=content)
    session.messages.create(role="assistant", content=reply_text, actions=results)

    # Sending into an ended session reopens it.
    if session.status == ChatSession.Status.ENDED:
        session.status = ChatSession.Status.ACTIVE
        session.ended_at = None
    session.save()

    session.refresh_from_db()
    return Response(ChatSessionSerializer(session).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_end_session(request, pk):
    """End a session and store an agent-generated summary for later resume."""
    session = _get_owned_session(request, pk)
    session.summary = summarize_session(session)
    session.status = ChatSession.Status.ENDED
    session.ended_at = timezone.now()
    session.save(update_fields=["summary", "status", "ended_at", "updated_at"])
    return Response(ChatSessionSerializer(session).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Customer support — Gemini agent with policy-gated, audited operations
# ---------------------------------------------------------------------------
class SupportSessionListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return SupportSession.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return SupportSessionListSerializer if self.request.method == "GET" else SupportSessionSerializer

    def create(self, request, *args, **kwargs):
        session = SupportSession.objects.create(user=request.user)
        return Response(SupportSessionSerializer(session).data, status=status.HTTP_201_CREATED)


class SupportSessionDetailView(generics.RetrieveAPIView):
    serializer_class = SupportSessionSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return SupportSession.objects.filter(user=self.request.user)


def _get_owned_support_session(request, pk):
    try:
        return SupportSession.objects.get(pk=pk, user=request.user)
    except SupportSession.DoesNotExist:
        raise NotFound("Support session not found.")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def support_send_message(request, pk):
    """Send a message to the support agent; run a Gemini turn; return the session."""
    session = _get_owned_support_session(request, pk)
    content = (request.data.get("content") or "").strip()
    if not content:
        return Response({"detail": "Message content is required."},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        reply_text, pending_operation = run_support_turn(session, content)
    except SupportAgentError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    session.messages.create(role="user", content=content)
    session.messages.create(role="assistant", content=reply_text)
    if session.status == SupportSession.Status.ENDED:
        session.status = SupportSession.Status.ACTIVE
        session.ended_at = None
    session.save()

    session.refresh_from_db()
    body = SupportSessionSerializer(session).data
    body["pending_operation"] = (
        SupportOperationSerializer(pending_operation).data if pending_operation else None
    )
    return Response(body, status=status.HTTP_200_OK)


def _get_owned_operation(request, op_id):
    try:
        return SupportOperation.objects.get(pk=op_id, user=request.user)
    except SupportOperation.DoesNotExist:
        raise NotFound("Operation not found.")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def support_confirm_operation(request, op_id):
    """Execute a pending operation after the user confirms it (policy re-checked)."""
    operation = _get_owned_operation(request, op_id)
    result = execute_operation(operation)
    operation.refresh_from_db()
    body = SupportOperationSerializer(operation).data
    body["result"] = result
    return Response(body, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def support_decline_operation(request, op_id):
    """Decline a pending operation — recorded, nothing is mutated."""
    operation = _get_owned_operation(request, op_id)
    result = decline_operation(operation)
    operation.refresh_from_db()
    body = SupportOperationSerializer(operation).data
    body["result"] = result
    return Response(body, status=status.HTTP_200_OK)

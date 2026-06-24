"""
agent.py — AI travel concierge backed by the OpenAI Codex CLI.

Each chat turn shells out to `codex exec` (non-interactive). The agent is *agentic*:
it can both fetch live data and mutate the user's trip, via a trailing JSON block.

Two kinds of requests the model can emit (in the json block):

  * "tool_calls" — read-only data lookups the backend runs against LiteAPI
    (live flight/hotel search). The backend executes them, feeds the results
    back into a follow-up Codex turn, and lets the model keep reasoning. This is
    a bounded loop (MAX_TOOL_ROUNDS), so the model can search → read → answer.
  * "actions" — whitelisted mutations of the user's data (book the selected
    hotel, change the budget tier, save the selection). These run once, after
    the model's final answer.

Codex itself runs read-only/sandboxed with native web search enabled; it never
touches our database directly — the backend is the only thing that calls LiteAPI
or writes to the DB, and only for the whitelisted tools/actions above.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


class AgentError(RuntimeError):
    """Raised when the Codex CLI fails or times out."""


# Whitelisted action types the agent may request (mutations, run after the reply).
VALID_ACTIONS = {"book_hotel", "book_flight", "set_budget_tier", "save_selection"}

# Whitelisted read-only tools the agent may call (live LiteAPI lookups).
VALID_TOOLS = {"search_flights", "search_hotels"}

# Cap on how many search→read→answer rounds one turn may take.
MAX_TOOL_ROUNDS = 3

_SYSTEM_PROMPT = (
    "You are Vantage Travel's AI concierge. You help one traveler plan and book a "
    "single trip. Be warm, concise, and concrete. You can use web search for "
    "real-time information (events, weather, opening hours, local tips) — do so "
    "when the user asks about current/real-world facts, and cite what you found.\n\n"
    "You are agentic: you can fetch LIVE flight/hotel availability and pricing from "
    "the app's booking provider (LiteAPI) and you can take real actions in the app. "
    "You do both by ending a reply with EXACTLY ONE fenced ```json block (and "
    "nothing after it).\n\n"
    "1) To look up live data, emit tool_calls — the app runs them and shows you the "
    "results, then you continue:\n"
    "```json\n"
    '{"tool_calls": [{"name": "search_hotels", "arguments": {}}]}\n'
    "```\n"
    "Available tools (arguments are optional; omit them to use the trip in CONTEXT):\n"
    '- "search_flights" args: origin_city, destination_city, departure_date, '
    "return_date, adults — live flight options by price tier.\n"
    '- "search_hotels" args: destination_city, destination_country, check_in, '
    "check_out, adults — live hotel options by price tier.\n"
    "Use these whenever the user asks about real prices, availability, or options — "
    "do not invent flights, hotels, or prices; look them up. After you receive "
    "TOOL RESULTS you may call more tools or give your final answer.\n\n"
    "2) To change the user's trip, emit actions (these run after your final reply):\n"
    "```json\n"
    '{"actions": [{"type": "book_hotel"}]}\n'
    "```\n"
    "Valid action types:\n"
    '- "book_hotel": book the user\'s currently selected hotel (only if one is '
    "selected in CONTEXT). Use when the user clearly asks to book/reserve it.\n"
    '- "book_flight": book the user\'s currently selected flight (only if one is '
    "selected in CONTEXT). Use when the user clearly asks to book/reserve it.\n"
    '- "set_budget_tier" with "tier" one of cheapest|affordable|moderate|luxury: '
    "change the user's budget category when they ask.\n"
    '- "save_selection": save the user\'s currently selected flight/hotel to their '
    "trip when they ask to keep/save it.\n\n"
    "Only include a json block when you actually need a tool or action; otherwise "
    "reply in plain prose with no json block. Never put both tool_calls and actions "
    "in the same block. Never invent booking references — the app fills those in."
)


class CodexAgentClient:
    """Thin wrapper over the `codex exec` non-interactive CLI."""

    def __init__(self):
        self.binary = getattr(settings, "CODEX_BINARY", "codex")
        self.model = getattr(settings, "CODEX_MODEL", "")
        self.timeout = int(getattr(settings, "CODEX_TIMEOUT_SECONDS", 180))

    def run(self, prompt: str) -> str:
        """Run one non-interactive Codex turn; return its final message text."""
        with tempfile.TemporaryDirectory(prefix="vantage_codex_") as workdir:
            out_path = os.path.join(workdir, "last_message.txt")
            cmd = [
                self.binary,
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "-s",
                "read-only",
                "--color",
                "never",
                "-c",
                "tools.web_search=true",
                "--cd",
                workdir,
                "--output-last-message",
                out_path,
                "-",  # read prompt from stdin
            ]
            if self.model:
                cmd[2:2] = ["-m", self.model]

            try:
                completed = subprocess.run(
                    cmd,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=workdir,
                )
            except FileNotFoundError as exc:
                raise AgentError("The Codex CLI is not installed on the server.") from exc
            except subprocess.TimeoutExpired as exc:
                raise AgentError("The assistant took too long to respond.") from exc

            if completed.returncode != 0:
                detail = (completed.stderr or "").strip()[-500:]
                raise AgentError(f"Codex exited with code {completed.returncode}: {detail}")

            try:
                with open(out_path, "r", encoding="utf-8") as handle:
                    message = handle.read().strip()
            except OSError:
                message = (completed.stdout or "").strip()

            if not message:
                raise AgentError("The assistant returned an empty response.")
            return message


def check_login_status() -> Tuple[bool, str]:
    """Return (is_logged_in, human_message) by asking the Codex CLI.

    Codex auth is machine-level (stored in ~/.codex/auth.json) and shared by all
    app users — the per-user separation is at the ChatSession layer, not here.
    """
    binary = getattr(settings, "CODEX_BINARY", "codex")
    try:
        completed = subprocess.run(
            [binary, "login", "status"],
            capture_output=True, text=True, timeout=20,
        )
    except FileNotFoundError:
        return False, f"Codex CLI '{binary}' is not installed on this server."
    except subprocess.TimeoutExpired:
        return False, "Codex login status check timed out."
    output = (completed.stdout or "").strip() or (completed.stderr or "").strip()
    ok = completed.returncode == 0 and "logged in" in output.lower()
    return ok, output or "Unknown Codex login status."


def log_login_status() -> None:
    """One-shot startup probe (run in a background thread) — never raises."""
    try:
        ok, message = check_login_status()
    except Exception as exc:  # noqa: BLE001 — diagnostics must not crash startup
        logger.warning("Codex login status check failed: %s", exc)
        return
    if ok:
        logger.info("Codex concierge ready — %s", message)
    else:
        logger.warning(
            "Codex concierge NOT authenticated (%s). Run `codex login` once on "
            "the server; the AI chat will return errors until then.", message,
        )


def _format_context(context: Dict[str, Any]) -> str:
    if not context:
        return "No trip context was provided."
    lines: List[str] = []
    origin = context.get("origin") or context.get("originCity")
    if origin:
        lines.append(f"- Origin / departure: {origin}")
    dest = context.get("destination") or context.get("destinationCity")
    if dest:
        country = context.get("destinationCountry")
        lines.append(f"- Destination: {dest}{', ' + country if country else ''}")
    if context.get("startDate") and context.get("endDate"):
        lines.append(f"- Dates: {context['startDate']} to {context['endDate']}")
    if context.get("travelers"):
        lines.append(f"- Travelers: {context['travelers']}")
    if context.get("budgetTier"):
        lines.append(f"- Budget category: {context['budgetTier']}")
    if context.get("interests"):
        interests = context["interests"]
        if isinstance(interests, list) and interests:
            lines.append(f"- Interests: {', '.join(map(str, interests))}")

    flight = context.get("selectedFlight")
    if isinstance(flight, dict) and flight:
        lines.append(
            f"- Selected flight: {flight.get('airline', 'unknown')} "
            f"({flight.get('origin', '?')}-{flight.get('destination', '?')}), "
            f"${flight.get('price', '?')}"
        )
    else:
        lines.append("- Selected flight: none")

    hotel = context.get("selectedHotel")
    if isinstance(hotel, dict) and hotel:
        lines.append(
            f"- Selected hotel: {hotel.get('name', 'unknown')} "
            f"(id: {hotel.get('id', '?')}), ${hotel.get('price', '?')} total, "
            f"{hotel.get('nights', '?')} night(s)"
        )
    else:
        lines.append("- Selected hotel: none")

    return "\n".join(lines)


def build_chat_prompt(
    context: Dict[str, Any],
    summary: str,
    history: List[Dict[str, str]],
    user_message: str,
) -> str:
    """Assemble the full single-shot prompt for one chat turn."""
    parts = [_SYSTEM_PROMPT, "\n\nCONTEXT (the user's trip):\n" + _format_context(context)]

    if summary:
        parts.append("\n\nSUMMARY OF EARLIER CONVERSATION:\n" + summary)

    if history:
        transcript = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in history
        )
        parts.append("\n\nRECENT MESSAGES:\n" + transcript)

    parts.append("\n\nUSER MESSAGE:\n" + user_message)
    parts.append(
        "\n\nReply directly to the user now. Remember the json action block rules."
    )
    return "".join(parts)


_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```\s*$", re.DOTALL)


def extract_block(raw_reply: str) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split a reply into (clean_text, tool_calls, actions).

    Tolerates a missing or malformed json block. Only whitelisted tool names /
    action types survive; anything else is dropped.
    """
    text = raw_reply.strip()
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return text, [], []

    clean = text[: match.start()].strip()
    try:
        payload = json.loads(match.group(1))
    except (json.JSONDecodeError, AttributeError):
        return clean, [], []
    if not isinstance(payload, dict):
        return clean, [], []

    raw_tools = payload.get("tool_calls") or []
    raw_actions = payload.get("actions") or []
    tools = [
        t for t in raw_tools
        if isinstance(t, dict) and t.get("name") in VALID_TOOLS
    ] if isinstance(raw_tools, list) else []
    actions = [
        a for a in raw_actions
        if isinstance(a, dict) and a.get("type") in VALID_ACTIONS
    ] if isinstance(raw_actions, list) else []
    return clean, tools, actions


def extract_actions(raw_reply: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Backwards-compatible helper: (clean_text, actions) only."""
    clean, _tools, actions = extract_block(raw_reply)
    return clean, actions


# ---------------------------------------------------------------------------
# Read-only tools — live LiteAPI lookups the agent can call mid-turn
# ---------------------------------------------------------------------------
def _ctx_get(context: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = context.get(key)
        if value:
            return value
    return None


def _summarize_options(tiers: Dict[str, Any], fields: List[str], per_tier: int = 3) -> Dict[str, Any]:
    """Trim a {tier: [options]} map to a compact, token-bounded summary."""
    out: Dict[str, Any] = {}
    if not isinstance(tiers, dict):
        return out
    for tier, options in tiers.items():
        if not isinstance(options, list):
            continue
        out[tier] = [
            {f: opt.get(f) for f in fields if f in opt}
            for opt in options[:per_tier]
            if isinstance(opt, dict)
        ]
    return out


def _tool_search_flights(context: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    from .services import FlightSearchInput, search_flight_options

    origin = args.get("origin_city") or _ctx_get(context, "origin", "originCity")
    destination = args.get("destination_city") or _ctx_get(context, "destination", "destinationCity")
    departure = args.get("departure_date") or context.get("startDate")
    return_date = args.get("return_date") or context.get("endDate")
    adults = int(args.get("adults") or context.get("travelers") or 1)
    currency = args.get("currency") or "USD"

    missing = [n for n, v in (
        ("origin_city", origin), ("destination_city", destination),
        ("departure_date", departure), ("return_date", return_date),
    ) if not v]
    if missing:
        return {"ok": False, "error": f"Missing required field(s): {', '.join(missing)}."}

    result = search_flight_options(FlightSearchInput(
        origin_city=origin, destination_city=destination,
        departure_date=departure, return_date=return_date,
        adults=adults, currency=currency,
    ))
    return {
        "ok": True,
        "origin": result.get("origin"),
        "destination": result.get("destination"),
        "currency": result.get("currency"),
        "options_by_tier": _summarize_options(
            result.get("tiers", {}),
            ["id", "airline", "price", "currency", "stops", "duration_minutes",
             "departure_time", "arrival_time", "round_trip", "outbound_price",
             "return_price", "return_airline", "return_departure_time",
             "return_arrival_time", "return_stops"],
        ),
    }


def _tool_search_hotels(context: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    from .services import HotelSearchInput, search_hotel_options

    destination = args.get("destination_city") or _ctx_get(context, "destination", "destinationCity")
    country = args.get("destination_country") or context.get("destinationCountry")
    check_in = args.get("check_in") or context.get("startDate")
    check_out = args.get("check_out") or context.get("endDate")
    adults = int(args.get("adults") or context.get("travelers") or 1)
    currency = args.get("currency") or "USD"

    missing = [n for n, v in (
        ("destination_city", destination), ("destination_country", country),
        ("check_in", check_in), ("check_out", check_out),
    ) if not v]
    if missing:
        return {"ok": False, "error": f"Missing required field(s): {', '.join(missing)}."}

    result = search_hotel_options(HotelSearchInput(
        destination_city=destination, destination_country=country,
        check_in=check_in, check_out=check_out,
        adults=adults, currency=currency,
    ))
    return {
        "ok": True,
        "destination_city": result.get("destination_city"),
        "destination_country": result.get("destination_country"),
        "currency": result.get("currency"),
        "nights": result.get("nights"),
        "options_by_tier": _summarize_options(
            result.get("tiers", {}),
            ["id", "name", "price", "currency", "nights", "stars", "rating",
             "board_name", "refundable", "address"],
        ),
    }


_TOOL_IMPLS = {
    "search_flights": _tool_search_flights,
    "search_hotels": _tool_search_hotels,
}


def execute_tools(context: Dict[str, Any], tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run requested read-only tools; return one result record per call."""
    results: List[Dict[str, Any]] = []
    for call in tool_calls:
        name = call.get("name")
        args = call.get("arguments")
        if not isinstance(args, dict):
            args = {}
        impl = _TOOL_IMPLS.get(name)
        if impl is None:
            results.append({"name": name, "ok": False, "error": "Unknown tool."})
            continue
        try:
            payload = impl(context, args)
        except ValueError as exc:
            payload = {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 — surface, never crash the turn
            payload = {"ok": False, "error": f"Lookup failed: {exc}"}
        payload["name"] = name
        results.append(payload)
    return results


def _current_trip(user):
    from .models import Trip

    return Trip.objects.filter(user=user).first()


def _book_selection(session, user, kind: str) -> Dict[str, Any]:
    """Book the selected flight/hotel idempotently; return a result record."""
    from .booking import Holder, book_offer

    context = session.context_snapshot or {}
    selection = context.get("selectedHotel" if kind == "hotel" else "selectedFlight") or {}
    offer_id = selection.get("id")
    label = selection.get("name") if kind == "hotel" else selection.get("airline")
    if not offer_id:
        return {"type": f"book_{kind}", "ok": False,
                "message": f"No {kind} is selected to book."}

    holder = Holder(
        first_name=(user.first_name or user.username or "Guest"),
        last_name=(user.last_name or "Traveler"),
        email=(user.email or "guest@example.com"),
    )
    booking, created = book_offer(
        user,
        kind=kind,
        offer_id=offer_id,
        holder=holder,
        title=str(label or "")[:255],
        price=selection.get("price"),
        currency=selection.get("currency", ""),
        airline=selection.get("airline", "") if kind == "flight" else "",
        trip=_current_trip(user),
        session=session,
    )
    verb = "Booked" if created else "Already booked"
    return {
        "type": f"book_{kind}", "ok": True,
        "message": f"{verb} {label or ('your ' + kind)} — ref {booking.reference} "
                   f"({booking.status}).",
        "data": {"reference": booking.reference, "status": booking.status,
                 "is_real": booking.is_real, "already_booked": not created},
    }


def execute_actions(
    session, actions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Run whitelisted actions against the user's data; return result records."""
    results: List[Dict[str, Any]] = []
    context = session.context_snapshot or {}
    user = session.user

    for action in actions:
        action_type = action.get("type")
        try:
            if action_type == "book_hotel":
                results.append(_book_selection(session, user, "hotel"))

            elif action_type == "book_flight":
                results.append(_book_selection(session, user, "flight"))

            elif action_type == "set_budget_tier":
                tier = (action.get("tier") or "").strip().lower()
                from .services import VALID_COMFORT_TIERS
                trip = _current_trip(user)
                if tier not in VALID_COMFORT_TIERS or trip is None:
                    results.append({"type": action_type, "ok": False,
                                    "message": "Could not change the budget category."})
                    continue
                trip.budget_profile = tier
                trip.save(update_fields=["budget_profile", "updated_at"])
                results.append({"type": action_type, "ok": True,
                                "message": f"Budget category set to {tier}."})

            elif action_type == "save_selection":
                trip = _current_trip(user)
                if trip is None:
                    results.append({"type": action_type, "ok": False,
                                    "message": "No saved trip to attach the selection to."})
                    continue
                flight = context.get("selectedFlight")
                hotel = context.get("selectedHotel")
                fields = []
                if isinstance(flight, dict) and flight:
                    trip.selected_flight = flight
                    fields.append("selected_flight")
                if isinstance(hotel, dict) and hotel:
                    trip.selected_hotel = hotel
                    fields.append("selected_hotel")
                if fields:
                    trip.save(update_fields=fields + ["updated_at"])
                    results.append({"type": action_type, "ok": True,
                                    "message": "Saved your selected options to the trip."})
                else:
                    results.append({"type": action_type, "ok": False,
                                    "message": "Nothing was selected to save."})
        except Exception as exc:  # noqa: BLE001 — never let an action crash the turn
            results.append({"type": action_type, "ok": False, "message": str(exc)})

    return results


def run_agent_turn(session, user_message: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Run one chat turn end to end.

    Drives the tool loop: Codex may ask for live LiteAPI data (tool_calls), the
    backend runs it and feeds the results back, and Codex keeps going until it
    answers in prose (or emits app actions). Returns (visible_text, action_results).
    """
    context = session.context_snapshot or {}
    # Verbatim window of the most recent turns; anything older is covered by the
    # session summary (regenerated on each end), so resumed sessions keep context.
    window = int(getattr(settings, "CODEX_HISTORY_WINDOW", 16))
    recent = list(
        session.messages.order_by("-created_at")[:window].values("role", "content")
    )
    recent.reverse()

    client = CodexAgentClient()
    prompt = build_chat_prompt(
        context=context,
        summary=session.summary or "",
        history=recent,
        user_message=user_message,
    )

    clean_text, actions = "", []
    for _ in range(MAX_TOOL_ROUNDS):
        raw_reply = client.run(prompt)
        clean_text, tool_calls, actions = extract_block(raw_reply)
        if not tool_calls:
            break
        # Run the requested lookups and feed the results back for another round.
        tool_results = execute_tools(context, tool_calls)
        prompt += (
            "\n\nASSISTANT (you requested tools):\n" + (clean_text or "(searching…)")
            + "\n\nTOOL RESULTS (JSON):\n" + json.dumps(tool_results, default=str)
            + "\n\nUsing these results, continue. Call more tools if needed, "
            "otherwise give your final answer to the user. Do not show raw JSON; "
            "summarize the relevant options in plain language."
        )
    else:
        # Ran out of rounds while still asking for tools — answer with what we have.
        if not clean_text:
            clean_text = (
                "I gathered some live options but ran out of lookup steps. "
                "Could you narrow down what you're after?"
            )

    action_results = execute_actions(session, actions) if actions else []

    # Append action outcomes to the visible reply so the user sees what happened.
    if action_results:
        suffix = "\n\n".join(
            ("✅ " if r.get("ok") else "⚠️ ") + r.get("message", "") for r in action_results
        )
        clean_text = f"{clean_text}\n\n{suffix}".strip()

    return clean_text, action_results


def summarize_session(session) -> str:
    """Ask Codex to summarize the transcript; used on session end + resume."""
    messages = list(session.messages.values("role", "content"))
    if not messages:
        return ""
    transcript = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)
    prompt = (
        "Summarize the following travel-planning conversation in 3-5 sentences. "
        "Capture the traveler's decisions, preferences, any bookings made, and open "
        "questions, so it can be used to resume the conversation later. Output only "
        "the summary text.\n\nCONVERSATION:\n" + transcript
    )
    try:
        return CodexAgentClient().run(prompt).strip()
    except AgentError:
        # Fall back to a trivial summary rather than failing the end-session call.
        return f"Conversation with {len(messages)} messages about the user's trip."

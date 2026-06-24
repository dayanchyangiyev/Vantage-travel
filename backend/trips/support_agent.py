"""
support_agent.py — customer-support agent backed by the Gemini API.

Uses a weaker Gemini model (default gemini-2.0-flash) with function calling. The
model can read the user's bookings and the policies, give advice, and — when
advice isn't enough — *propose* a refund or modification. Proposals are gated:
the backend checks policy + ownership (support_policies / support_ops) and records
a SupportOperation that the user must explicitly confirm. The model never mutates
data directly.

Gemini is called over REST (no extra dependency) via services._http_request_json,
with the API key sent as the `x-goog-api-key` header (kept out of logs by the
api_logging redactor).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

from .services import _http_request_json
from .support_policies import POLICIES
from .support_ops import propose_modification, propose_refund

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5

_SYSTEM_PROMPT = (
    "You are Vantage Travel's customer support agent. You help one signed-in "
    "customer with problems about their trips and bookings. Be warm, concise, and "
    "accurate. Resolve with advice and recommendations first.\n\n"
    "You operate in two modes:\n"
    "- ASSIST: answer questions, troubleshoot, and recommend. Use get_my_bookings "
    "to ground answers in the customer's real bookings, and get_policies when a "
    "rule is relevant.\n"
    "- INDIVIDUAL: when advice cannot solve the problem and the customer wants an "
    "action, you may propose ONE operation with propose_refund or "
    "propose_modification. These do NOT execute immediately — they create a "
    "request the customer must confirm in the app. Always tell the customer what "
    "you are about to do and that they must confirm.\n\n"
    "Rules: only ever discuss or act on THIS customer's own bookings. Never invent "
    "booking references, prices, confirmation codes, or policies — look them up. "
    "Never claim an operation is done; only the confirmation step completes it. "
    "Follow the company policies below.\n\n" + POLICIES
)

# Gemini function declarations for the tools the agent may call.
_TOOL_DECLARATIONS = [
    {
        "name": "get_my_bookings",
        "description": "List the signed-in customer's bookings (flights and hotels) "
                       "with reference, status, price, and trip dates.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_policies",
        "description": "Return Vantage Travel's customer support, refund, and "
                       "modification policies.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "propose_refund",
        "description": "Propose refunding one of the customer's bookings. Creates a "
                       "request the customer must confirm; does not refund directly.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "booking_reference": {"type": "STRING", "description": "The booking reference to refund."},
                "reason": {"type": "STRING", "description": "The customer's reason for the refund."},
            },
            "required": ["booking_reference", "reason"],
        },
    },
    {
        "name": "propose_modification",
        "description": "Propose modifying one of the customer's bookings (e.g. change "
                       "dates). Creates a request the customer must confirm.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "booking_reference": {"type": "STRING", "description": "The booking reference to modify."},
                "change_description": {"type": "STRING", "description": "The change the customer wants."},
            },
            "required": ["booking_reference", "change_description"],
        },
    },
]


class SupportAgentError(RuntimeError):
    """Raised when the Gemini API call fails."""


class GeminiClient:
    """Thin REST wrapper over Gemini generateContent with function calling."""

    def __init__(self):
        self.api_key = getattr(settings, "GEMINI_API_KEY", "")
        self.model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
        self.base_url = getattr(
            settings, "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")
        self.timeout = int(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 60))

    def generate(self, contents: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.api_key:
            raise SupportAgentError("GEMINI_API_KEY is not configured on the server.")
        url = f"{self.base_url}/models/{self.model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": contents,
            "tools": [{"functionDeclarations": _TOOL_DECLARATIONS}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
        }
        try:
            return _http_request_json(
                "POST", url,
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                payload=payload,
            )
        except Exception as exc:  # noqa: BLE001 — normalize to a friendly error
            logger.warning("Gemini request failed: %s", exc)
            raise SupportAgentError("The support assistant is temporarily unavailable.") from exc


def _history_contents(session) -> List[Dict[str, Any]]:
    """Build Gemini `contents` from the session's recent messages."""
    window = int(getattr(settings, "GEMINI_HISTORY_WINDOW", 20))
    recent = list(
        session.messages.order_by("-created_at")[:window].values("role", "content")
    )
    recent.reverse()
    contents: List[Dict[str, Any]] = []
    for m in recent:
        if m["role"] not in ("user", "assistant"):
            continue
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    return contents


def _bookings_for(user) -> List[Dict[str, Any]]:
    from .models import Booking
    rows = Booking.objects.filter(user=user).select_related("trip")
    out = []
    for b in rows:
        out.append({
            "reference": b.reference,
            "kind": b.kind,
            "title": b.title,
            "status": b.status,
            "price": float(b.price) if b.price is not None else None,
            "currency": b.currency,
            "trip_start": b.trip.start_date.isoformat() if b.trip and b.trip.start_date else None,
            "trip_end": b.trip.end_date.isoformat() if b.trip and b.trip.end_date else None,
        })
    return out


def _execute_tool(
    session, user, name: str, args: Dict[str, Any]
) -> Tuple[Dict[str, Any], Optional["SupportOperation"]]:  # noqa: F821
    """Run one tool call. Returns (response_for_model, pending_operation_or_None)."""
    if name == "get_my_bookings":
        return {"bookings": _bookings_for(user)}, None
    if name == "get_policies":
        return {"policies": POLICIES}, None
    if name == "propose_refund":
        op, result = propose_refund(user, session, args.get("booking_reference", ""), args.get("reason", ""))
        return result, (op if (op and result.get("requires_confirmation")) else None)
    if name == "propose_modification":
        op, result = propose_modification(user, session, args.get("booking_reference", ""), args.get("change_description", ""))
        return result, (op if (op and result.get("requires_confirmation")) else None)
    return {"ok": False, "message": f"Unknown tool '{name}'."}, None


def _parts_text(parts: List[Dict[str, Any]]) -> str:
    return "\n".join(p["text"] for p in parts if "text" in p).strip()


def run_support_turn(session, user_message: str):
    """Run one support turn end to end.

    Drives the Gemini function-calling loop; returns (reply_text, pending_operation).
    pending_operation is a SupportOperation awaiting the user's confirmation, or None.
    """
    client = GeminiClient()
    user = session.user
    contents = _history_contents(session)
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    reply_text = ""
    pending_operation = None

    for _ in range(MAX_TOOL_ROUNDS):
        data = client.generate(contents)
        candidates = data.get("candidates") or []
        if not candidates:
            reply_text = "Sorry, I couldn't process that. Could you rephrase?"
            break
        parts = (candidates[0].get("content") or {}).get("parts") or []
        function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

        if not function_calls:
            reply_text = _parts_text(parts) or "How else can I help?"
            break

        # Echo the model's function-call turn, then answer each call.
        contents.append({"role": "model", "parts": parts})
        response_parts = []
        for call in function_calls:
            result, op = _execute_tool(session, user, name=call.get("name", ""), args=call.get("args") or {})
            if op is not None:
                pending_operation = op
            response_parts.append({
                "functionResponse": {"name": call.get("name", ""), "response": result}
            })
        contents.append({"role": "user", "parts": response_parts})
    else:
        if not reply_text:
            reply_text = "I've gathered what I can — could you clarify what you'd like to do next?"

    # A proposed operation flips the session into individual (agent) mode and gets a
    # clear confirmation prompt (the weak model sometimes returns only filler text).
    if pending_operation is not None:
        if session.mode != session.Mode.INDIVIDUAL:
            session.mode = session.Mode.INDIVIDUAL
        ref = pending_operation.booking.reference if pending_operation.booking else "your booking"
        verb = "refund" if pending_operation.kind == "refund" else "change"
        confirm_line = (
            f"I've prepared a {verb} for booking {ref}. "
            "Please review and confirm below to proceed."
        )
        if not reply_text or reply_text in ("How else can I help?",
                                            "I've gathered what I can — could you clarify what you'd like to do next?"):
            reply_text = confirm_line
        elif "confirm" not in reply_text.lower():
            reply_text = f"{reply_text}\n\n{confirm_line}"

    return reply_text, pending_operation

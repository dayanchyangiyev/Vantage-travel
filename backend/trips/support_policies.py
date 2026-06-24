"""
support_policies.py — company + security policies for the customer-support agent.

The Gemini support agent may *propose* operations (refunds, modifications) but the
backend is the authority: these functions decide whether an operation is permitted,
and the human-readable `POLICIES` text is shown to the agent (and users) so its
recommendations stay within policy. Every decision returns the clause it relied on,
which is stored on the SupportOperation as `policy_basis` for audit.
"""

from __future__ import annotations

from datetime import date
from typing import Tuple

# Statuses considered "active" (i.e. still refundable / modifiable).
ACTIVE_STATUSES = {"CONFIRMED", "PENDING"}

# Shown to the agent in its system prompt and returned by the get_policies tool.
POLICIES = """Vantage Travel — Customer Support Policies

Security
- S1. You may only view or act on bookings that belong to the signed-in user. Never
  reveal or touch another customer's data.
- S2. Never invent booking references, prices, confirmation codes, or policy rules.
- S3. High-impact operations (refunds, modifications) are NEVER performed automatically.
  They require an explicit user confirmation step, which the app handles for you.

Refunds
- R1. Refunds apply only to the user's own active booking (not already cancelled,
  refunded, or modification-pending).
- R2. A refund is permitted only before the trip's start date. Once the trip has
  started, refunds must be escalated to a human and cannot be self-served.
- R3. The user must provide a reason for the refund.
- R4. Refunds are recorded against the booking; the booking is marked REFUNDED.

Modifications
- M1. Modifications apply only to the user's own active booking, before the trip start.
- M2. The user must describe the desired change. The change is logged as a request and
  the booking is flagged for follow-up; it is not re-charged automatically.

Conduct
- C1. Be concise, warm, and accurate. Resolve with advice first. Only escalate to an
  operation when advice cannot solve the problem and the user wants the action.
"""


def _trip_started(booking) -> bool:
    """True if the booking's trip has already started (so it's too late to refund)."""
    trip = getattr(booking, "trip", None)
    start = getattr(trip, "start_date", None)
    return bool(start and start <= date.today())


def _is_active(booking) -> bool:
    return (booking.status or "").upper() in ACTIVE_STATUSES


def evaluate_refund(user, booking, reason: str = "") -> Tuple[bool, str]:
    """Decide whether `user` may refund `booking`. Returns (allowed, policy_basis)."""
    if booking is None or booking.user_id != getattr(user, "id", None):
        return False, "S1: a booking can only be refunded by the customer who owns it."
    if not _is_active(booking):
        return False, f"R1: booking {booking.reference} is {booking.status} and not refundable."
    if _trip_started(booking):
        return False, "R2: the trip has already started; refunds require a human agent."
    if not (reason or "").strip():
        return False, "R3: a reason is required to process a refund."
    return True, "R1–R4: own active booking, before trip start, reason provided — refund permitted."


def evaluate_modification(user, booking, change_description: str = "") -> Tuple[bool, str]:
    """Decide whether `user` may modify `booking`. Returns (allowed, policy_basis)."""
    if booking is None or booking.user_id != getattr(user, "id", None):
        return False, "S1: a booking can only be modified by the customer who owns it."
    if not _is_active(booking):
        return False, f"M1: booking {booking.reference} is {booking.status} and not modifiable."
    if _trip_started(booking):
        return False, "M1: the trip has already started; modifications require a human agent."
    if not (change_description or "").strip():
        return False, "M2: a description of the desired change is required."
    return True, "M1–M2: own active booking, before trip start, change described — modification request permitted."

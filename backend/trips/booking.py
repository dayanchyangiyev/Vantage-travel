"""
booking.py — one place that turns a selected offer into a persisted Booking.

Both the checkout HTTP endpoint and the AI agent go through `book_offer`, so the
idempotency guard (don't re-book the same offer for the same user) and the
persistence are identical no matter who triggers the booking.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

from .models import Booking
from .services import (
    FlightBookingInput,
    HotelBookingInput,
    create_flight_booking,
    create_hotel_booking,
)


@dataclass(frozen=True)
class Holder:
    first_name: str
    last_name: str
    email: str


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def find_active_booking(user, kind: str, offer_id: str) -> Optional[Booking]:
    """Return a non-cancelled booking for this user+offer, if one exists."""
    if not offer_id:
        return None
    return (
        Booking.objects.filter(user=user, kind=kind, offer_id=offer_id)
        .exclude(status="CANCELLED")
        .first()
    )


def book_offer(
    user,
    *,
    kind: str,
    offer_id: str,
    holder: Holder,
    title: str = "",
    price: Any = None,
    currency: str = "",
    airline: str = "",
    trip=None,
    session=None,
    extra: Optional[Dict[str, Any]] = None,
) -> Tuple[Booking, bool]:
    """Book an offer and persist it. Returns (booking, created).

    `created` is False when an active booking for the same user+offer already
    existed — the supplier is NOT called again. This is what stops a new chat
    session (or a double click) from re-booking something already booked.
    """
    if kind not in (Booking.Kind.FLIGHT, Booking.Kind.HOTEL):
        raise ValueError(f"Unknown booking kind: {kind!r}")
    if not offer_id:
        raise ValueError("An offer is required to book.")

    existing = find_active_booking(user, kind, offer_id)
    if existing is not None:
        return existing, False

    if kind == Booking.Kind.HOTEL:
        confirmation = create_hotel_booking(
            HotelBookingInput(
                offer_id=offer_id,
                first_name=holder.first_name,
                last_name=holder.last_name,
                email=holder.email,
            )
        )
        is_real = True
    else:
        confirmation = create_flight_booking(
            FlightBookingInput(
                offer_id=offer_id,
                first_name=holder.first_name,
                last_name=holder.last_name,
                email=holder.email,
                airline=airline,
                price=float(price) if _to_decimal(price) is not None else None,
                currency=currency or "USD",
            )
        )
        is_real = False

    booking = Booking.objects.create(
        user=user,
        trip=trip,
        session=session,
        kind=kind,
        offer_id=offer_id,
        reference=confirmation["booking_id"],
        supplier_reference=confirmation.get("supplier_booking_id") or "",
        status=confirmation.get("status") or "CONFIRMED",
        title=title,
        price=_to_decimal(confirmation.get("price")) or _to_decimal(price),
        currency=confirmation.get("currency") or currency or "",
        is_real=is_real,
        details={**(extra or {}), "confirmation": confirmation},
    )
    return booking, True

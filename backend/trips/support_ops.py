"""
support_ops.py — propose + execute customer-support operations.

The support agent calls the `propose_*` helpers (via Gemini function calls). They
NEVER mutate a booking — they validate ownership + policy and record a
SupportOperation that is `awaiting_confirmation` (or `denied`). Execution happens
only after the user explicitly confirms, through `execute_operation`, which
re-validates server-side and writes before/after state for audit.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from django.utils import timezone

from .models import Booking, SupportOperation
from .support_policies import evaluate_modification, evaluate_refund


def _booking_state(booking: Booking) -> Dict[str, Any]:
    return {
        "reference": booking.reference,
        "kind": booking.kind,
        "status": booking.status,
        "title": booking.title,
        "price": float(booking.price) if booking.price is not None else None,
        "currency": booking.currency,
    }


def find_booking(user, reference: str) -> Optional[Booking]:
    if not reference:
        return None
    return Booking.objects.filter(user=user, reference=reference.strip()).first()


def _propose(
    user, session, kind: str, reference: str, reason: str,
    evaluator, details: Dict[str, Any],
) -> Tuple[Optional[SupportOperation], Dict[str, Any]]:
    """Shared proposal flow: locate booking, check policy, record the operation."""
    booking = find_booking(user, reference)
    if booking is None:
        # No operation row for a non-existent target — just tell the agent.
        return None, {
            "ok": False,
            "message": f"No booking found with reference '{reference}' on your account.",
        }

    allowed, basis = evaluator(user, booking, reason)
    op = SupportOperation.objects.create(
        user=user,
        session=session,
        booking=booking,
        kind=kind,
        status=(SupportOperation.Status.AWAITING_CONFIRMATION if allowed
                else SupportOperation.Status.DENIED),
        reason=reason or "",
        policy_basis=basis,
        details=details,
        before_state=_booking_state(booking),
    )
    if not allowed:
        return op, {"ok": False, "operation_id": op.id, "denied": True,
                    "policy_basis": basis,
                    "message": f"That isn't permitted: {basis}"}
    return op, {
        "ok": True,
        "operation_id": op.id,
        "requires_confirmation": True,
        "booking": _booking_state(booking),
        "policy_basis": basis,
        "message": (f"Ready to {kind} booking {booking.reference} "
                    f"({booking.title or booking.kind}). Awaiting the customer's confirmation."),
    }


def propose_refund(user, session, booking_reference: str, reason: str) -> Tuple[Optional[SupportOperation], Dict[str, Any]]:
    return _propose(
        user, session, SupportOperation.Kind.REFUND, booking_reference, reason,
        evaluate_refund, details={"reason": reason},
    )


def propose_modification(user, session, booking_reference: str, change_description: str) -> Tuple[Optional[SupportOperation], Dict[str, Any]]:
    return _propose(
        user, session, SupportOperation.Kind.MODIFY, booking_reference, change_description,
        evaluate_modification, details={"change_description": change_description},
    )


def execute_operation(operation: SupportOperation) -> Dict[str, Any]:
    """Execute a confirmed operation. Re-validates policy + ownership server-side.

    Idempotent: an already-executed operation just returns its result. Never trusts
    the model or client — the policy is checked again here before any mutation.
    """
    if operation.status == SupportOperation.Status.EXECUTED:
        return {"ok": True, "already_done": True, "message": "This operation was already completed."}
    if operation.status != SupportOperation.Status.AWAITING_CONFIRMATION:
        return {"ok": False, "message": f"This operation cannot be executed (state: {operation.status})."}

    booking = operation.booking
    if booking is None or booking.user_id != operation.user_id:
        operation.status = SupportOperation.Status.FAILED
        operation.save(update_fields=["status"])
        return {"ok": False, "message": "The target booking is no longer available."}

    # Re-validate against current state — the world may have changed since the proposal.
    if operation.kind == SupportOperation.Kind.REFUND:
        allowed, basis = evaluate_refund(operation.user, booking, operation.reason)
    else:
        allowed, basis = evaluate_modification(operation.user, booking, operation.reason)
    if not allowed:
        operation.status = SupportOperation.Status.DENIED
        operation.policy_basis = basis
        operation.save(update_fields=["status", "policy_basis"])
        return {"ok": False, "denied": True, "message": f"No longer permitted: {basis}"}

    operation.before_state = _booking_state(booking)

    if operation.kind == SupportOperation.Kind.REFUND:
        booking.status = "REFUNDED"
        booking.details = {**(booking.details or {}), "refund": {
            "reason": operation.reason, "operation_id": operation.id,
        }}
        booking.save(update_fields=["status", "details"])
        message = f"Booking {booking.reference} has been refunded."
    else:
        booking.status = "MODIFICATION_REQUESTED"
        booking.details = {**(booking.details or {}), "modification_request": {
            "change": operation.details.get("change_description", ""),
            "operation_id": operation.id,
        }}
        booking.save(update_fields=["status", "details"])
        message = (f"Your change request for booking {booking.reference} has been logged; "
                   f"our team will follow up to finalize it.")

    operation.after_state = _booking_state(booking)
    operation.status = SupportOperation.Status.EXECUTED
    operation.policy_basis = basis
    operation.executed_at = timezone.now()
    operation.save(update_fields=[
        "before_state", "after_state", "status", "policy_basis", "executed_at",
    ])
    return {"ok": True, "operation_id": operation.id, "message": message,
            "booking": _booking_state(booking)}


def decline_operation(operation: SupportOperation) -> Dict[str, Any]:
    """User declined a pending operation — record it, mutate nothing."""
    if operation.status == SupportOperation.Status.AWAITING_CONFIRMATION:
        operation.status = SupportOperation.Status.DECLINED
        operation.save(update_fields=["status"])
    return {"ok": True, "message": "Okay, I won't make that change."}

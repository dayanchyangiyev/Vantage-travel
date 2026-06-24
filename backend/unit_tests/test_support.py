"""
test_support.py — customer-support agent: policies, operation execution, and the
session/message/confirm endpoints. The Gemini HTTP call is always mocked.
"""

from datetime import date, timedelta

import pytest
from django.urls import reverse


def _make_booking(user, *, status="CONFIRMED", days_ahead=30, reference="VTG-ABC123"):
    from trips.models import Booking, Trip
    trip = Trip.objects.create(
        user=user, destination="Paris, France", travelers=2,
        start_date=date.today() + timedelta(days=days_ahead),
        end_date=date.today() + timedelta(days=days_ahead + 4),
    )
    return Booking.objects.create(
        user=user, trip=trip, kind="hotel", offer_id="off-1", reference=reference,
        status=status, title="Hôtel Test", price=200, currency="USD", is_real=True,
    )


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
class TestSupportPolicies:
    def test_refund_allowed_for_own_future_active_booking(self, test_user):
        from trips.support_policies import evaluate_refund
        booking = _make_booking(test_user)
        allowed, basis = evaluate_refund(test_user, booking, "flight got cancelled")
        assert allowed is True
        assert "permitted" in basis.lower()

    def test_refund_denied_without_reason(self, test_user):
        from trips.support_policies import evaluate_refund
        booking = _make_booking(test_user)
        allowed, basis = evaluate_refund(test_user, booking, "")
        assert allowed is False
        assert "reason" in basis.lower()

    def test_refund_denied_after_trip_started(self, test_user):
        from trips.support_policies import evaluate_refund
        booking = _make_booking(test_user, days_ahead=-2)
        allowed, basis = evaluate_refund(test_user, booking, "changed plans")
        assert allowed is False
        assert "started" in basis.lower()

    def test_refund_denied_for_other_users_booking(self, test_user, django_user_model):
        from trips.support_policies import evaluate_refund
        other = django_user_model.objects.create_user(username="intruder", password="x")
        booking = _make_booking(test_user)
        allowed, _ = evaluate_refund(other, booking, "not mine")
        assert allowed is False

    def test_refund_denied_when_already_refunded(self, test_user):
        from trips.support_policies import evaluate_refund
        booking = _make_booking(test_user, status="REFUNDED")
        allowed, _ = evaluate_refund(test_user, booking, "again?")
        assert allowed is False


# ---------------------------------------------------------------------------
# Operation execution
# ---------------------------------------------------------------------------
class TestSupportOps:
    def test_propose_then_execute_refund(self, test_user):
        from trips.support_ops import execute_operation, propose_refund
        from trips.models import Booking, SupportOperation
        booking = _make_booking(test_user)

        op, result = propose_refund(test_user, None, booking.reference, "supplier closed")
        assert result["requires_confirmation"] is True
        assert op.status == SupportOperation.Status.AWAITING_CONFIRMATION

        out = execute_operation(op)
        op.refresh_from_db()
        booking.refresh_from_db()
        assert out["ok"] is True
        assert booking.status == "REFUNDED"
        assert op.status == SupportOperation.Status.EXECUTED
        assert op.before_state["status"] == "CONFIRMED"
        assert op.after_state["status"] == "REFUNDED"
        assert op.executed_at is not None

    def test_execute_is_idempotent(self, test_user):
        from trips.support_ops import execute_operation, propose_refund
        booking = _make_booking(test_user)
        op, _ = propose_refund(test_user, None, booking.reference, "reason")
        execute_operation(op)
        second = execute_operation(op)
        assert second.get("already_done") is True

    def test_propose_unknown_booking_creates_no_operation(self, test_user):
        from trips.support_ops import propose_refund
        from trips.models import SupportOperation
        op, result = propose_refund(test_user, None, "VTG-NOPE", "reason")
        assert op is None
        assert result["ok"] is False
        assert SupportOperation.objects.count() == 0

    def test_denied_proposal_is_recorded_but_not_executable(self, test_user):
        from trips.support_ops import execute_operation, propose_refund
        from trips.models import SupportOperation
        booking = _make_booking(test_user, days_ahead=-1)  # trip already started
        op, result = propose_refund(test_user, None, booking.reference, "late")
        assert result["denied"] is True
        assert op.status == SupportOperation.Status.DENIED
        out = execute_operation(op)
        assert out["ok"] is False

    def test_decline_operation(self, test_user):
        from trips.support_ops import decline_operation, propose_refund
        from trips.models import SupportOperation
        booking = _make_booking(test_user)
        op, _ = propose_refund(test_user, None, booking.reference, "reason")
        decline_operation(op)
        op.refresh_from_db()
        assert op.status == SupportOperation.Status.DECLINED


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def _gemini_function_call(name, args):
    return {"candidates": [{"content": {"role": "model", "parts": [
        {"functionCall": {"name": name, "args": args}}
    ]}}]}


def _gemini_text(text):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}


class TestSupportEndpoints:
    def test_session_create_requires_auth(self, api_client):
        resp = api_client.post(reverse("support-session-list"))
        assert resp.status_code in (401, 403)

    def test_message_assist_reply(self, auth_client, test_user, mocker):
        mocker.patch("trips.support_agent.GeminiClient.generate",
                     return_value=_gemini_text("Happy to help! What's the issue?"))
        session = auth_client.post(reverse("support-session-list")).data
        resp = auth_client.post(
            reverse("support-send-message", args=[session["id"]]),
            {"content": "hello"}, format="json",
        )
        assert resp.status_code == 200
        assert resp.data["pending_operation"] is None
        assert len(resp.data["messages"]) == 2  # user + assistant

    def test_message_proposes_refund_then_confirm(self, auth_client, test_user, mocker):
        booking = _make_booking(test_user)
        mocker.patch(
            "trips.support_agent.GeminiClient.generate",
            side_effect=[
                _gemini_function_call("propose_refund", {
                    "booking_reference": booking.reference, "reason": "supplier cancelled"}),
                _gemini_text("I've prepared the refund — please confirm."),
            ],
        )
        session = auth_client.post(reverse("support-session-list")).data
        resp = auth_client.post(
            reverse("support-send-message", args=[session["id"]]),
            {"content": "please refund my hotel"}, format="json",
        )
        assert resp.status_code == 200
        pending = resp.data["pending_operation"]
        assert pending is not None
        assert pending["kind"] == "refund"
        assert pending["status"] == "awaiting_confirmation"
        assert resp.data["mode"] == "individual"  # escalated

        confirm = auth_client.post(reverse("support-confirm-op", args=[pending["id"]]))
        assert confirm.status_code == 200
        assert confirm.data["status"] == "executed"
        booking.refresh_from_db()
        assert booking.status == "REFUNDED"

    def test_confirm_other_users_operation_is_404(self, auth_client, django_user_model):
        """A user cannot confirm an operation that belongs to someone else."""
        from trips.models import SupportOperation, SupportSession
        other = django_user_model.objects.create_user(username="mallory", password="x")
        session = SupportSession.objects.create(user=other)
        op = SupportOperation.objects.create(
            user=other, session=session, kind="refund",
            status=SupportOperation.Status.AWAITING_CONFIRMATION,
        )
        resp = auth_client.post(reverse("support-confirm-op", args=[op.id]))
        assert resp.status_code == 404

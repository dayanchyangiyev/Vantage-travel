from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Trip(models.Model):
    class BudgetProfile(models.TextChoices):
        CHEAPEST = "cheapest", "Cheapest"
        AFFORDABLE = "affordable", "Affordable"
        MODERATE = "moderate", "Moderate"
        LUXURY = "luxury", "Luxury"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trips",
    )
    origin_country = models.CharField(max_length=120, default="")
    destination = models.CharField(max_length=255)
    travelers = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    budget_profile = models.CharField(
        max_length=20,
        choices=BudgetProfile.choices,
        default=BudgetProfile.MODERATE,
    )
    interests = models.JSONField(default=list, blank=True)
    engine_output = models.JSONField(default=dict, blank=True)
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    selected_flight = models.JSONField(null=True, blank=True, default=None)
    selected_hotel = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="trip_end_date_gte_start_date",
            ),
        ]
        ordering = ["-created_at", "-id"]

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must be on or after start date."})

    def __str__(self):
        return (
            f"{self.destination} ({self.start_date} to {self.end_date}) "
            f"for {self.user}"
        )


class ChatSession(models.Model):
    """A conversation with the AI travel concierge (Codex agent)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    title = models.CharField(max_length=160, default="New conversation")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    # Snapshot of the user's trip context (preferences + chosen flight/hotel +
    # pricing tier) captured when the session starts; the agent reads this.
    context_snapshot = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"ChatSession #{self.pk} ({self.status}) for {self.user}"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    # Executed agent actions + their results (e.g. a booking confirmation).
    actions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.role} message in session #{self.session_id}"


class Booking(models.Model):
    """A flight or hotel booking made by a user.

    Hotels book for real against the LiteAPI sandbox; flights are recorded as
    demo confirmations (live flight offers expire within minutes). Persisting
    these lets us show a user's bookings and avoid re-booking the same offer
    (e.g. when the AI agent is asked to book again in a new chat session).
    """

    class Kind(models.TextChoices):
        FLIGHT = "flight", "Flight"
        HOTEL = "hotel", "Hotel"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    trip = models.ForeignKey(
        Trip, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings",
    )
    session = models.ForeignKey(
        ChatSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # The provider offer id this booking was made from — used for idempotency.
    offer_id = models.CharField(max_length=512)
    reference = models.CharField(max_length=128)
    supplier_reference = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=32, default="CONFIRMED")
    title = models.CharField(max_length=255, blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, blank=True, default="")
    # True when confirmed with a real supplier (hotels); False for demo (flights).
    is_real = models.BooleanField(default=False)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # One active booking per user per offer — the guard against re-booking.
            models.UniqueConstraint(
                fields=["user", "kind", "offer_id"],
                condition=~Q(status="CANCELLED"),
                name="unique_active_booking_per_offer",
            )
        ]

    def __str__(self):
        return f"{self.kind} booking {self.reference} for {self.user}"

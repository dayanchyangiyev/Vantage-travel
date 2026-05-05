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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="trip_end_date_gte_start_date",
            ),
        ]
        ordering = ["-created_at"]

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must be on or after start date."})

    def __str__(self):
        return (
            f"{self.destination} ({self.start_date} to {self.end_date}) "
            f"for {self.user}"
        )

from decimal import Decimal

from rest_framework import serializers

from .models import Trip
from .services import VALID_COMFORT_TIERS


class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = (
            "id",
            "user",
            "origin_country",
            "destination",
            "travelers",
            "start_date",
            "end_date",
            "budget_profile",
            "interests",
            "engine_output",
            "pricing_snapshot",
            "selected_flight",
            "selected_hotel",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        origin_country = attrs.get("origin_country")

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be on or after start date."}
            )

        if origin_country is not None and not origin_country.strip():
            raise serializers.ValidationError(
                {"origin_country": "Origin country cannot be empty."}
            )

        snapshot = attrs.get("pricing_snapshot")
        if snapshot is not None and snapshot != {}:
            if not isinstance(snapshot, dict):
                raise serializers.ValidationError(
                    {"pricing_snapshot": "Pricing snapshot must be a JSON object."}
                )
            tiers = snapshot.get("tiers")
            if not isinstance(tiers, dict):
                raise serializers.ValidationError(
                    {"pricing_snapshot": "Pricing snapshot must include tiers."}
                )
            required_tiers = {"cheapest", "affordable", "moderate", "luxury"}
            if not required_tiers.issubset(set(tiers.keys())):
                raise serializers.ValidationError(
                    {"pricing_snapshot": "Pricing tiers are incomplete."}
                )

        return attrs


class BudgetTierQuerySerializer(serializers.Serializer):
    origin_city = serializers.CharField()
    destination_city = serializers.CharField()
    destination_country = serializers.CharField()
    departure_date = serializers.DateField()
    return_date = serializers.DateField()
    adults = serializers.IntegerField(min_value=1, default=1)
    currency = serializers.CharField(required=False, default="USD")


class BudgetEvaluationInputSerializer(serializers.Serializer):
    origin_city = serializers.CharField()
    destination_city = serializers.CharField()
    destination_country = serializers.CharField()
    departure_date = serializers.DateField()
    return_date = serializers.DateField()
    adults = serializers.IntegerField(min_value=1, default=1)
    max_flight_budget = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))
    total_living_budget = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))
    comfort_preference = serializers.ChoiceField(choices=sorted(VALID_COMFORT_TIERS))
    currency = serializers.CharField(required=False, default="USD")


class WeatherQuerySerializer(serializers.Serializer):
    destination_city = serializers.CharField()
    destination_country = serializers.CharField()
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)


class FlightSearchQuerySerializer(serializers.Serializer):
    origin_city = serializers.CharField()
    destination_city = serializers.CharField()
    departure_date = serializers.DateField()
    return_date = serializers.DateField()
    adults = serializers.IntegerField(min_value=1, default=1)
    currency = serializers.CharField(required=False, default="USD")


class HotelSearchQuerySerializer(serializers.Serializer):
    destination_city = serializers.CharField()
    destination_country = serializers.CharField()
    check_in = serializers.DateField()
    check_out = serializers.DateField()
    adults = serializers.IntegerField(min_value=1, default=1)
    currency = serializers.CharField(required=False, default="USD")


class HotelBookingSerializer(serializers.Serializer):
    offer_id = serializers.CharField()
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    email = serializers.EmailField()

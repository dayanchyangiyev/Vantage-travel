from rest_framework import serializers

from .models import Trip


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

        return attrs

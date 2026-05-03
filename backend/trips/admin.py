from django.contrib import admin

from .models import Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "origin_country",
        "destination",
        "travelers",
        "budget_profile",
        "start_date",
        "end_date",
        "created_at",
    )
    list_filter = ("budget_profile", "start_date", "end_date", "created_at")
    search_fields = ("origin_country", "destination", "user__username", "user__email")

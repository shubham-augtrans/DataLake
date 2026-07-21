from django.contrib import admin

from .models import DataDestination


@admin.register(DataDestination)
class DataDestinationAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "destination_type",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "destination_type",
    )

    list_filter = (
        "destination_type",
        "is_active",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)
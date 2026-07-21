from django.contrib import admin

from .models import IngestionPipeline


@admin.register(IngestionPipeline)
class IngestionPipelineAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "source",
        "destination",
        "sync_interval",
        "created_at",
    )

    list_filter = (
        "source",
        "destination",
    )

    search_fields = (
        "name",
        "source__name",
        "destination__name",
    )

    ordering = ("-created_at",)
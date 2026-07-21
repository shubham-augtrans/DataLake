from django.contrib import admin
from .models import DataSource


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "source_type",
        "is_active",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "source_type",
    )

    list_filter = (
        "source_type",
        "is_active",
        "created_at",
        "updated_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)
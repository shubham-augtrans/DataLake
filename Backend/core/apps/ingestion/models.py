from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.data_sources.models import DataSource
from apps.data_destination.models import DataDestination


class IngestionPipeline(models.Model):
    name = models.CharField(max_length=255)

    source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="pipelines"
    )

    destination = models.ForeignKey(
        DataDestination,
        on_delete=models.CASCADE,
        related_name="pipelines"
    )

    sync_interval = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(24)
        ],
        help_text="Sync interval in hours (1-24)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ingestion_pipeline"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
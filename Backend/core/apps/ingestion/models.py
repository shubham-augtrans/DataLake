from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.data_sources.models import DataSource
from apps.data_destination.models import DataDestination


class IngestionPipeline(models.Model):
    name = models.CharField(max_length=255)

    source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="pipelines",
    )

    destination = models.ForeignKey(
        DataDestination,
        on_delete=models.CASCADE,
        related_name="pipelines",
    )

    sync_interval = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(24),
        ],
        help_text="Sync interval in hours (1-24)",
    )

    # Table name, topic name, or collection name to ingest - meaning depends on
    # source.source_type, same pattern as DataSource.source_type/configuration.
    source_object = models.CharField(
        max_length=255,
        blank=True,
    )

    # NiFi references
    nifi_process_group_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    nifi_source_processor_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    nifi_destination_processor_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    nifi_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    nifi_last_error = models.TextField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ingestion_pipeline"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class PipelineRun(models.Model):
    """
    One execution of a pipeline's /run/ action - lets the frontend show
    which pipelines are ACTUALLY running right now (RUNNING rows), rather
    than just the pipeline's static config. Runs are synchronous (the /run/
    request blocks until this finishes - see PipelineService.run()), so a
    row only stays RUNNING for the lifetime of that one HTTP request.
    """

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    pipeline = models.ForeignKey(
        IngestionPipeline,
        on_delete=models.CASCADE,
        related_name="runs",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
    )

    triggered_by = models.CharField(
        max_length=50,
        default="manual",
        help_text="e.g. 'manual' (UI/API) or 'airflow' (scheduled DAG).",
    )

    message = models.TextField(null=True, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pipeline_run"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.pipeline.name} [{self.status}]"
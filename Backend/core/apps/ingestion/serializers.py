from django.utils import timezone
from rest_framework import serializers

from .models import IngestionPipeline, PipelineRun


class IngestionPipelineSerializer(serializers.ModelSerializer):

    source_name = serializers.CharField(source="source.name", read_only=True)
    destination_name = serializers.CharField(
        source="destination.name",
        read_only=True
    )

    class Meta:
        model = IngestionPipeline
        fields = [
            "id",
            "name",
            "source",
            "source_name",
            "destination",
            "destination_name",
            "source_object",
            "sync_interval",
            "nifi_status",
            "nifi_last_error",
            "created_at",
            "updated_at",
        ]


class PipelineRunSerializer(serializers.ModelSerializer):

    pipeline_name = serializers.CharField(source="pipeline.name", read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = PipelineRun
        fields = [
            "id",
            "pipeline",
            "pipeline_name",
            "status",
            "triggered_by",
            "message",
            "started_at",
            "finished_at",
            "duration_seconds",
        ]

    def get_duration_seconds(self, obj):
        end = obj.finished_at or timezone.now()
        return round((end - obj.started_at).total_seconds(), 1)
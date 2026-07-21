from rest_framework import serializers

from .models import IngestionPipeline


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
            "sync_interval",
            "created_at",
            "updated_at",
        ]
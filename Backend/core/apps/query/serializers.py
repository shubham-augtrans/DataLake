from rest_framework import serializers

from .models import QueryHistory


class QueryHistorySerializer(serializers.ModelSerializer):

    data_source_name = serializers.SerializerMethodField()

    def get_data_source_name(self, obj):
        return obj.data_source.name if obj.data_source_id else "Trino"

    class Meta:
        model = QueryHistory
        fields = [
            "id",
            "data_source",
            "data_source_name",
            "trino_user",
            "sql_text",
            "status",
            "row_count",
            "duration_ms",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields


class ExecuteQuerySerializer(serializers.Serializer):
    data_source = serializers.IntegerField()
    sql = serializers.CharField()


class ExecuteTrinoQuerySerializer(serializers.Serializer):
    sql = serializers.CharField()

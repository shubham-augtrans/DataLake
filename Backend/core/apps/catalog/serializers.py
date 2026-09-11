from rest_framework import serializers

from .models import DataDictionaryEntry


class DataDictionaryEntrySerializer(serializers.ModelSerializer):

    updated_by_email = serializers.SerializerMethodField()

    def get_updated_by_email(self, obj):
        return obj.updated_by.email if obj.updated_by_id else None

    class Meta:
        model = DataDictionaryEntry
        fields = [
            "id",
            "namespace",
            "table_name",
            "column_name",
            "description",
            "updated_by_email",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_by_email", "updated_at"]


class DataDictionaryUpsertSerializer(serializers.Serializer):
    namespace = serializers.CharField()
    table = serializers.CharField()
    column = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(allow_blank=True)

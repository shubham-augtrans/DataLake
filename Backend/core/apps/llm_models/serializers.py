from rest_framework import serializers

from .models import LLMModel


class LLMModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMModel
        fields = [
            "id",
            "name",
            "api_base",
            "model_name",
            "api_key",
            "ca_cert",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

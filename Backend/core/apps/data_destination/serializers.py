from rest_framework import serializers

from .models import DataDestination


class DataDestinationSerializer(serializers.ModelSerializer):

    class Meta:
        model = DataDestination
        fields = "__all__"
        read_only_fields = (
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):

        destination_type = attrs.get("destination_type")
        config = attrs.get("configuration", {})

        required_fields = {

            "postgresql": [
                "host",
                "port",
                "database",
                "username",
                "password",
            ],

            "mysql": [
                "host",
                "port",
                "database",
                "username",
                "password",
            ],

            "sqlserver": [
                "host",
                "port",
                "database",
                "username",
                "password",
            ],

            "oracle": [
                "host",
                "port",
                "service_name",
                "username",
                "password",
            ],

            "snowflake": [
                "account",
                "warehouse",
                "database",
                "schema",
                "username",
                "password",
            ],

            "delta_lake": [
                "path"
            ],

            "minio": [
                "endpoint",
                "access_key",
                "secret_key",
            ],

            "aws_s3": [
                "region",
                "bucket",
                "access_key",
                "secret_key",
            ],

            "azure_blob": [
                "account_name",
                "container",
                "connection_string",
            ],
        }

        if destination_type in required_fields:

            missing = [
                field
                for field in required_fields[destination_type]
                if field not in config or config[field] in ("", None)
            ]

            if missing:
                raise serializers.ValidationError({
                    "configuration":
                        f"Missing required fields: {', '.join(missing)}"
                })

        return attrs
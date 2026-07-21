from django.db import models


class DataDestination(models.Model):

    DESTINATION_TYPES = [
        ("postgresql", "PostgreSQL"),
        ("mysql", "MySQL"),
         ("mongo", "MongoDB"),
        ("sqlserver", "SQL Server"),
        ("oracle", "Oracle"),
        ("snowflake", "Snowflake"),
        ("delta_lake", "Delta Lake"),
        ("aws_s3", "AWS S3"),
        ("azure_blob", "Azure Blob"),
        ("minio", "MinIO"),
    ]

    name = models.CharField(max_length=255)

    destination_type = models.CharField(
        max_length=50,
        choices=DESTINATION_TYPES
    )

    configuration = models.JSONField(default=dict)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
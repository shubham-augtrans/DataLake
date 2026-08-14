from django.db import models


class DataSource(models.Model):

    SOURCE_TYPES = [
        ("mongo", "MongoDB"),
        ("postgres", "PostgreSQL"),
        # ("postgresql", "PostgreSQL"),
        # ("minio", "MinIO"),
        # ("aws_s3", "AWS S3"),
        # ("azure_blob", "Azure Blob"),
        # ("mysql", "MySQL"),
        # ("sqlserver", "SQL Server"),
        # ("oracle", "Oracle"),
        # ("sharepoint", "SharePoint"),
        # ("rest_api", "REST API"),
        # ("ftp", "FTP"),
        # ("sftp", "SFTP"),
    ]

    name = models.CharField(max_length=255)

    source_type = models.CharField(
        max_length=50,
        choices=SOURCE_TYPES
    )

    configuration = models.JSONField(default=dict)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
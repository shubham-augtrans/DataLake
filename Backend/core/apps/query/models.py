from django.db import models

from apps.data_sources.models import DataSource


class QueryHistory(models.Model):

    STATUS_CHOICES = [
        ("success", "Success"),
        ("error", "Error"),
        ("denied", "Denied"),
    ]

    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="query_history",
        null=True,
        blank=True,
    )

    # Set for queries executed via Trino instead of a configured DataSource -
    # the Django-authenticated user's derived Trino/Ranger identity.
    trino_user = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    sql_text = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
    )

    row_count = models.IntegerField(
        null=True,
        blank=True,
    )

    duration_ms = models.IntegerField(
        null=True,
        blank=True,
    )

    error_message = models.TextField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "query_history"
        ordering = ["-created_at"]
        verbose_name_plural = "Query history"

    def __str__(self):
        return f"{self.data_source_id} @ {self.created_at}"

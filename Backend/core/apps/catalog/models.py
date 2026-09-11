from django.conf import settings
from django.db import models


class DataDictionaryEntry(models.Model):
    """
    Human-authored description for an Iceberg table or one of its columns.
    Iceberg's own metadata only carries name/type - this fills the business
    meaning gap so users browsing the catalog know what a table/column
    actually holds. column_name = "" means the description is for the
    table itself rather than a specific column.
    """

    namespace = models.CharField(max_length=255)
    table_name = models.CharField(max_length=255)
    column_name = models.CharField(max_length=255, blank=True, default="")

    description = models.TextField()

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_dictionary_entry"
        unique_together = ("namespace", "table_name", "column_name")
        verbose_name_plural = "Data dictionary entries"

    def __str__(self):
        target = f"{self.namespace}.{self.table_name}"
        if self.column_name:
            target += f".{self.column_name}"
        return target

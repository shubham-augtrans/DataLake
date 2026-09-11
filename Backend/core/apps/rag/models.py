from django.db import models

from apps.ingestion.models import IngestionPipeline


class RagChunk(models.Model):
    """
    One text chunk extracted from a PDF that an ingestion pipeline landed as
    a raw file (IngestionPipeline.ingest_mode == "file") - see
    apps.rag.services.ingest_pipeline_document(). Retrieval scores chunks
    against a question with TF-IDF (services.retrieve_chunks) rather than
    real embeddings, since the org's hosted LLM endpoint only serves chat
    completions, not an embeddings API.
    """

    pipeline = models.ForeignKey(
        IngestionPipeline,
        on_delete=models.CASCADE,
        related_name="rag_chunks",
    )

    chunk_index = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rag_chunk"
        ordering = ["pipeline_id", "chunk_index"]
        indexes = [models.Index(fields=["pipeline"])]

    def __str__(self):
        return f"{self.pipeline.name} #{self.chunk_index}"

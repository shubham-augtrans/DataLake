from django.db import models


class LLMModel(models.Model):
    """
    A configured LLM endpoint (OpenAI-compatible) the app can call for
    prompt-to-SQL generation - replaces the old LLM_API_BASE/LLM_API_TOKEN/
    LLM_MODEL/LLM_CA_CERT_PATH .env settings, so models can be added/swapped
    from the UI instead of editing .env and restarting the server.
    """

    name = models.CharField(max_length=255)
    api_base = models.CharField(max_length=500)
    model_name = models.CharField(max_length=255)
    api_key = models.CharField(max_length=2000, blank=True)
    ca_cert = models.TextField(
        blank=True,
        help_text="PEM-encoded CA certificate, only needed if the endpoint's "
                   "TLS certificate isn't signed by a publicly trusted CA.",
    )
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "llm_models"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            LLMModel.objects.exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)

import os
import tempfile

import requests

from .models import LLMModel

LLM_TIMEOUT = 60


class LLMClientError(Exception):
    pass


def get_default_llm_model():
    model = LLMModel.objects.filter(is_default=True).first()

    if not model:
        raise LLMClientError(
            "No default LLM model is configured. Add one under AI/ML -> "
            "Models and mark it as default."
        )

    return model


def call_llm(prompt_text, temperature=0):
    """
    Sends `prompt_text` as a single user message to whichever LLMModel is
    marked as the default (configured under AI/ML -> Models, not .env) and
    returns the raw text of its reply. Shared by every feature that needs a
    one-shot LLM completion - Playground's prompt-to-SQL and RAG Chat's
    retrieval-grounded answers both go through this one model config.
    """
    model = get_default_llm_model()

    headers = {}
    if model.api_key:
        headers["Authorization"] = f"Bearer {model.api_key}"

    # `verify` needs a filesystem path, not the PEM text itself - write it
    # to a throwaway file for the duration of this one request.
    cert_file = None
    verify = True

    try:
        if model.ca_cert:
            cert_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".crt", delete=False
            )
            cert_file.write(model.ca_cert)
            cert_file.close()
            verify = cert_file.name

        response = requests.post(
            f"{model.api_base.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": model.model_name,
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": temperature,
            },
            verify=verify,
            timeout=LLM_TIMEOUT,
        )
        response.raise_for_status()

    except requests.RequestException as ex:
        raise LLMClientError(f"Failed to reach the LLM: {str(ex)}")

    finally:
        if cert_file:
            os.unlink(cert_file.name)

    try:
        return response.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise LLMClientError("The LLM returned an unexpected response shape.")

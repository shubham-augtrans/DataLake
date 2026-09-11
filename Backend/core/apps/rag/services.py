import io

import boto3
from django.db.models import Count
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from apps.ingestion.models import IngestionPipeline
from apps.llm_models.client import LLMClientError, call_llm

from .models import RagChunk

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
TOP_K = 5


class RagError(Exception):
    pass


def _minio_client(pipeline):
    config = pipeline.destination.configuration
    return boto3.client(
        "s3",
        endpoint_url=config["endpoint"],
        aws_access_key_id=config["access_key"],
        aws_secret_access_key=config["secret_key"],
    )


def _download_pdf_bytes(pipeline):
    if pipeline.ingest_mode != "file" or not pipeline.raw_object_key:
        raise RagError(f"'{pipeline.name}' has no raw file to read.")

    if pipeline.raw_content_type != "application/pdf":
        raise RagError(
            f"'{pipeline.name}' is not a PDF ({pipeline.raw_content_type or 'unknown type'})."
        )

    client = _minio_client(pipeline)

    try:
        obj = client.get_object(Bucket=pipeline.raw_object_bucket, Key=pipeline.raw_object_key)
    except client.exceptions.NoSuchKey:
        raise RagError(f"'{pipeline.name}''s file is no longer in MinIO.")

    return obj["Body"].read()


def _extract_pages(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []

    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((i, text))

    return pages


def _chunk_page_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end])
        if end == length:
            break
        start = end - overlap

    return chunks


def ingest_pipeline_document(pipeline):
    """
    Extracts text from the PDF this pipeline landed in MinIO, splits it into
    overlapping chunks per page, and replaces any chunks already stored for
    it - a re-ingest fully replaces, never appends. Returns the chunk count.
    """
    pdf_bytes = _download_pdf_bytes(pipeline)
    pages = _extract_pages(pdf_bytes)

    if not pages:
        raise RagError(
            f"Could not extract any text from '{pipeline.name}' - it may be a "
            f"scanned/image-only PDF with no selectable text."
        )

    RagChunk.objects.filter(pipeline=pipeline).delete()

    chunks = []
    index = 0
    for page_number, page_text in pages:
        for piece in _chunk_page_text(page_text):
            chunks.append(RagChunk(
                pipeline=pipeline,
                chunk_index=index,
                page_number=page_number,
                text=piece,
            ))
            index += 1

    RagChunk.objects.bulk_create(chunks)
    return len(chunks)


def list_documents():
    """
    Every ingestion pipeline that landed a PDF as a raw file - these are the
    documents RAG Chat can be asked about. chunk_count == 0 means it hasn't
    been ingested (extracted + chunked + stored) yet.
    """
    pipelines = list(
        IngestionPipeline.objects.filter(
            ingest_mode="file", raw_content_type="application/pdf",
        ).select_related("source").order_by("-created_at")
    )

    chunk_counts = dict(
        RagChunk.objects.filter(pipeline__in=pipelines)
        .values("pipeline_id")
        .annotate(count=Count("id"))
        .values_list("pipeline_id", "count")
    )

    return [
        {
            "pipeline_id": p.id,
            "name": p.name,
            "filename": p.source_object,
            "source_name": p.source.name,
            "chunk_count": chunk_counts.get(p.id, 0),
        }
        for p in pipelines
    ]


def retrieve_chunks(question, pipeline_ids=None, top_k=TOP_K):
    """
    Scores every candidate chunk against the question with TF-IDF cosine
    similarity and returns the top matches. Not real semantic search (no
    embedding model is available on the org's hosted LLM endpoint - it only
    serves chat completions) but keyword-level TF-IDF is a reasonable,
    zero-extra-infra stand-in for a handful of PDFs.
    """
    qs = RagChunk.objects.select_related("pipeline")
    if pipeline_ids:
        qs = qs.filter(pipeline_id__in=pipeline_ids)

    chunks = list(qs)
    if not chunks:
        return []

    texts = [c.text for c in chunks]
    vectorizer = TfidfVectorizer(stop_words="english")

    try:
        matrix = vectorizer.fit_transform(texts + [question])
    except ValueError:
        # Empty vocabulary (e.g. the question is only stopwords) - nothing
        # meaningful to score against.
        return []

    doc_vectors, question_vector = matrix[:-1], matrix[-1]
    scores = cosine_similarity(question_vector, doc_vectors)[0]

    ranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)
    return [(chunk, float(score)) for chunk, score in ranked[:top_k] if score > 0]


def answer_question(question, pipeline_ids=None, history=None):
    """
    Retrieval-augmented answer: ingests any requested document that hasn't
    been chunked yet (so picking a PDF and immediately asking about it just
    works), retrieves the most relevant chunks, and asks the same default
    LLM Playground uses (apps.llm_models.client.call_llm) to answer grounded
    only in those excerpts.
    """
    if pipeline_ids:
        pipelines = list(IngestionPipeline.objects.filter(id__in=pipeline_ids))
        missing = set(pipeline_ids) - {p.id for p in pipelines}
        if missing:
            raise RagError(f"Unknown document id(s): {sorted(missing)}")

        for pipeline in pipelines:
            if not RagChunk.objects.filter(pipeline=pipeline).exists():
                ingest_pipeline_document(pipeline)

    matches = retrieve_chunks(question, pipeline_ids=pipeline_ids)

    if not matches:
        return {
            "answer": "I couldn't find anything relevant to that in the selected document(s).",
            "sources": [],
        }

    context_block = "\n\n".join(
        f"[Source: {chunk.pipeline.name}, page {chunk.page_number}]\n{chunk.text}"
        for chunk, _ in matches
    )

    history_block = ""
    if history:
        numbered = "\n".join(
            f"{i + 1}. Q: {turn['question']}\n   A: {turn['answer']}"
            for i, turn in enumerate(history)
        )
        history_block = f"Conversation so far (oldest first):\n{numbered}\n\n"

    prompt = (
        "You are a document Q&A assistant. Answer the question using ONLY "
        "the excerpts below - if the excerpts don't contain the answer, say "
        "so plainly instead of guessing. Cite the source page(s) you used "
        "inline like (page 3).\n\n"
        f"{history_block}"
        f"Excerpts:\n{context_block}\n\n"
        f"Question: {question}\n\nAnswer:"
    )

    try:
        answer = call_llm(prompt).strip()
    except LLMClientError as ex:
        raise RagError(str(ex))

    sources = [
        {
            "pipeline_id": chunk.pipeline_id,
            "pipeline_name": chunk.pipeline.name,
            "page_number": chunk.page_number,
            "score": round(score, 3),
            "snippet": chunk.text[:240],
        }
        for chunk, score in matches
    ]

    return {"answer": answer, "sources": sources}

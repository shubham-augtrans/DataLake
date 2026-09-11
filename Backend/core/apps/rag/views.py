from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ingestion.models import IngestionPipeline

from .services import RagError, answer_question, ingest_pipeline_document, list_documents


class RagDocumentsView(APIView):
    """
    Lists the PDFs available to chat with - every ingestion pipeline that
    landed a PDF as a raw file (see apps.ingestion's Google Drive raw-file
    path).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(list_documents())


class RagDocumentIngestView(APIView):
    """
    Explicitly (re-)extracts and chunks one document. Not required before
    chatting - RagChatView ingests on first use automatically - but lets the
    UI show a "ready" state up front, or force a re-ingest after the source
    file changed.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        try:
            pipeline = IngestionPipeline.objects.get(pk=pk)
        except IngestionPipeline.DoesNotExist:
            return Response({"error": "Pipeline not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            chunk_count = ingest_pipeline_document(pipeline)
        except RagError as ex:
            return Response({"error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"pipeline_id": pipeline.id, "chunk_count": chunk_count})


class RagChatView(APIView):
    """
    One RAG turn: retrieves the most relevant chunks from the selected
    document(s) (or every ingested document, if none are named) and asks
    the default LLM model to answer grounded in them.
    """

    permission_classes = [IsAuthenticated]

    MAX_HISTORY_TURNS = 6

    def post(self, request):
        question = (request.data.get("question") or "").strip()

        if not question:
            return Response(
                {"error": "question is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_pipeline_ids = request.data.get("pipeline_ids") or []
        try:
            pipeline_ids = [int(pid) for pid in raw_pipeline_ids] or None
        except (TypeError, ValueError):
            return Response(
                {"error": "pipeline_ids must be a list of integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_history = request.data.get("history") or []
        history = [
            {"question": str(turn.get("question", "")).strip(), "answer": str(turn.get("answer", "")).strip()}
            for turn in raw_history
            if isinstance(turn, dict) and turn.get("question") and turn.get("answer")
        ][-self.MAX_HISTORY_TURNS:]

        try:
            result = answer_question(question, pipeline_ids=pipeline_ids, history=history)
        except RagError as ex:
            return Response({"error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "question": question,
            "answer": result["answer"],
            "sources": result["sources"],
        })

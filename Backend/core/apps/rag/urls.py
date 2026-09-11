from django.urls import path

from .views import RagChatView, RagDocumentIngestView, RagDocumentsView

urlpatterns = [
    path("documents/", RagDocumentsView.as_view(), name="rag-documents"),
    path("documents/<int:pk>/ingest/", RagDocumentIngestView.as_view(), name="rag-document-ingest"),
    path("chat/", RagChatView.as_view(), name="rag-chat"),
]

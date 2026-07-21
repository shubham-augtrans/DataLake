from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import IngestionPipelineViewSet

router = DefaultRouter()
router.register(
    r"",
    IngestionPipelineViewSet,
    basename="ingestion-pipeline"
)

urlpatterns = [
    path("", include(router.urls)),
]
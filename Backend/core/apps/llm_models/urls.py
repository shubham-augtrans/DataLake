from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LLMModelViewSet

router = DefaultRouter()
router.register(r"", LLMModelViewSet, basename="llm-model")

urlpatterns = [
    path("", include(router.urls)),
]

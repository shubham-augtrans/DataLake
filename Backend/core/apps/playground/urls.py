from django.urls import path

from .views import PromptToDashboardView

urlpatterns = [
    path("generate/", PromptToDashboardView.as_view(), name="playground-generate"),
]

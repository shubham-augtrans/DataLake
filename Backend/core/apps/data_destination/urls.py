from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DataDestinationViewSet

router = DefaultRouter()
router.register(r"", DataDestinationViewSet)
    
urlpatterns = [
    path("", include(router.urls)),
]
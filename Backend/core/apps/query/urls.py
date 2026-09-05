from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ExecuteQueryView, ExecuteTrinoQueryView, QueryHistoryViewSet

router = DefaultRouter()
router.register(
    r"history",
    QueryHistoryViewSet,
    basename="query-history",
)

urlpatterns = [
    path("execute/", ExecuteQueryView.as_view(), name="query-execute"),
    path("execute-trino/", ExecuteTrinoQueryView.as_view(), name="query-execute-trino"),
    path("", include(router.urls)),
]

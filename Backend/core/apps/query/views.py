from rest_framework import status, viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data_sources.models import DataSource

from .models import QueryHistory
from .serializers import (
    ExecuteQuerySerializer,
    ExecuteTrinoQuerySerializer,
    QueryHistorySerializer,
)
from .services import (
    PostgresQueryRunner,
    QueryAuthorizationError,
    QueryExecutionError,
    TrinoQueryRunner,
)


class ExecuteQueryView(APIView):

    def post(self, request):

        serializer = ExecuteQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data_source_id = serializer.validated_data["data_source"]
        sql_text = serializer.validated_data["sql"]

        try:
            datasource = DataSource.objects.get(pk=data_source_id)
        except DataSource.DoesNotExist:
            return Response(
                {"error": "Data source not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            runner = PostgresQueryRunner(datasource)
            result = runner.run(sql_text)

            QueryHistory.objects.create(
                data_source=datasource,
                sql_text=sql_text,
                status="success",
                row_count=result["row_count"],
                duration_ms=result["duration_ms"],
            )

            return Response(result, status=status.HTTP_200_OK)

        except QueryExecutionError as ex:

            QueryHistory.objects.create(
                data_source=datasource,
                sql_text=sql_text,
                status="error",
                error_message=str(ex),
            )

            return Response(
                {"error": str(ex)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ExecuteTrinoQueryView(APIView):
    """
    Runs SQL against Trino as the authenticated Django user's own identity,
    so that Apache Ranger's policies (configured in the `dev_trino` service)
    are evaluated per-user rather than through a shared account. Requires
    authentication - governance is meaningless if the caller is anonymous.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = ExecuteTrinoQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sql_text = serializer.validated_data["sql"]

        # Derive the Trino/Ranger username from the authenticated user's
        # email local-part (e.g. shubham@datalake.local -> "shubham").
        trino_user = request.user.email.split("@")[0]

        try:
            result = TrinoQueryRunner(trino_user).run(sql_text)

            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=sql_text,
                status="success",
                row_count=result["row_count"],
                duration_ms=result["duration_ms"],
            )

            return Response(result, status=status.HTTP_200_OK)

        except QueryAuthorizationError as ex:

            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=sql_text,
                status="denied",
                error_message=str(ex),
            )

            return Response(
                {"error": str(ex)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except QueryExecutionError as ex:

            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=sql_text,
                status="error",
                error_message=str(ex),
            )

            return Response(
                {"error": str(ex)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class QueryHistoryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = QueryHistory.objects.select_related("data_source").all()
    serializer_class = QueryHistorySerializer

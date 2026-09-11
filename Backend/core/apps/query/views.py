from rest_framework import status, viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import QueryHistory
from .serializers import (
    ExecuteQuerySerializer,
    ExecuteTrinoQuerySerializer,
    QueryHistorySerializer,
)
from .services import (
    LAKEHOUSE_SCHEMA,
    QueryAuthorizationError,
    QueryExecutionError,
    TrinoQueryRunner,
)


class ExecuteQueryView(APIView):
    """
    The SQL Editor's execute endpoint. Runs against the lakehouse (Iceberg
    tables backed by MinIO) via Trino, the same governed path as the Trino
    Editor - not a direct connection to a source database. Defaults the
    session to the `ingested` schema so unqualified table names (e.g.
    `SELECT * FROM orders`) resolve to the ingested copy without requiring
    `iceberg.ingested.orders`.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = ExecuteQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sql_text = serializer.validated_data["sql"]

        trino_user = request.user.email.split("@")[0]

        try:
            result = TrinoQueryRunner(trino_user, schema=LAKEHOUSE_SCHEMA).run(sql_text)

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


class TrinoSchemaExplorerView(APIView):
    """
    Backs the Trino editor's schema explorer tree (catalogs -> schemas ->
    tables -> columns). Every listing runs through TrinoQueryRunner as the
    authenticated user, so it only ever shows what Ranger allows them to see.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):

        trino_user = request.user.email.split("@")[0]
        runner = TrinoQueryRunner(trino_user)

        catalog = request.query_params.get("catalog")
        schema = request.query_params.get("schema")
        table = request.query_params.get("table")

        try:
            if table:
                if not (catalog and schema):
                    return Response(
                        {"error": "catalog and schema are required with table."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                return Response({"columns": runner.list_columns(catalog, schema, table)})

            if schema:
                if not catalog:
                    return Response(
                        {"error": "catalog is required with schema."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                return Response({"tables": runner.list_tables(catalog, schema)})

            if catalog:
                return Response({"schemas": runner.list_schemas(catalog)})

            return Response({"catalogs": runner.list_catalogs()})

        except QueryAuthorizationError as ex:
            return Response({"error": str(ex)}, status=status.HTTP_403_FORBIDDEN)

        except QueryExecutionError as ex:
            return Response({"error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


class QueryHistoryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = QueryHistory.objects.select_related("data_source").all()
    serializer_class = QueryHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        source = self.request.query_params.get("source")

        if source == "trino":
            queryset = queryset.filter(trino_user__isnull=False)
        elif source == "postgres":
            queryset = queryset.filter(data_source__isnull=False)

        return queryset

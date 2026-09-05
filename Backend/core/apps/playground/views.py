from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data_sources.models import DataSource
from apps.query.models import QueryHistory
from apps.query.services import PostgresQueryRunner, QueryExecutionError

from .services import (
    PromptToSqlError,
    fetch_schema_summary,
    generate_sql,
    infer_chart,
)


class PromptToDashboardView(APIView):

    def post(self, request):
        data_source_id = request.data.get("data_source")
        prompt = (request.data.get("prompt") or "").strip()

        if not data_source_id or not prompt:
            return Response(
                {"error": "data_source and prompt are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            datasource = DataSource.objects.get(pk=data_source_id)
        except DataSource.DoesNotExist:
            return Response(
                {"error": "Data source not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            schema_summary = fetch_schema_summary(datasource)
            sql = generate_sql(datasource, prompt, schema_summary)

            result = PostgresQueryRunner(datasource).run(sql)
            chart = infer_chart(result["columns"], result["rows"])

            QueryHistory.objects.create(
                data_source=datasource,
                sql_text=f"-- prompt: {prompt}\n{sql}",
                status="success",
                row_count=result["row_count"],
                duration_ms=result["duration_ms"],
            )

            return Response({
                "prompt": prompt,
                "sql": sql,
                "columns": result["columns"],
                "rows": result["rows"],
                "row_count": result["row_count"],
                "truncated": result["truncated"],
                "duration_ms": result["duration_ms"],
                "chart": chart,
            })

        except (PromptToSqlError, QueryExecutionError) as ex:
            QueryHistory.objects.create(
                data_source=datasource,
                sql_text=f"-- prompt: {prompt}",
                status="error",
                error_message=str(ex),
            )

            return Response(
                {"error": str(ex)},
                status=status.HTTP_400_BAD_REQUEST,
            )

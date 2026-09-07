from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data_sources.models import DataSource
from apps.query.models import QueryHistory
from apps.query.services import QueryExecutionError

from .metabase_client import MetabaseClient, MetabaseError
from .services import build_widget, decompose_prompt, fetch_schema_summary


class PromptToDashboardView(APIView):
    """
    Turns a prompt into a real Metabase dashboard: decomposes it into a few
    chartable sub-questions, runs each against the DataSource, and creates a
    Metabase Card + Dashboard for the results - rendering happens in Metabase,
    not in this app.
    """

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
        except QueryExecutionError as ex:
            return Response({"error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            metabase = MetabaseClient()
            database_id = metabase.find_database_id(datasource)
        except MetabaseError as ex:
            return Response({"error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

        sub_questions = decompose_prompt(prompt, schema_summary)

        widgets = []
        card_ids = []

        for sub_question in sub_questions:
            widget = build_widget(
                datasource,
                sub_question["title"],
                sub_question["question"],
                schema_summary,
            )
            widgets.append(widget)

            if "error" in widget:
                QueryHistory.objects.create(
                    data_source=datasource,
                    sql_text=f"-- prompt: {prompt} :: {widget['title']}",
                    status="error",
                    error_message=widget["error"],
                )
                continue

            try:
                card = metabase.create_card(
                    database_id=database_id,
                    name=widget["title"],
                    sql=widget["sql"],
                    display=metabase.chart_to_display(widget["chart"]["type"]),
                )
                card_ids.append(card["id"])

                QueryHistory.objects.create(
                    data_source=datasource,
                    sql_text=f"-- prompt: {prompt} :: {widget['title']}\n{widget['sql']}",
                    status="success",
                    row_count=widget["row_count"],
                    duration_ms=widget["duration_ms"],
                )

            except MetabaseError as ex:
                widget.pop("columns", None)
                widget.pop("rows", None)
                widget["error"] = f"Query ran but Metabase card creation failed: {ex}"

        if not card_ids:
            return Response(
                {"error": "No widgets could be created.", "widgets": widgets},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dashboard = metabase.create_dashboard(name=f"AI: {prompt[:60]}")
        metabase.add_cards_to_dashboard(dashboard["id"], card_ids)

        return Response({
            "prompt": prompt,
            "dashboard_url": metabase.dashboard_url(dashboard["id"]),
            "widgets": [
                {
                    "title": w["title"],
                    "sql": w.get("sql"),
                    "row_count": w.get("row_count"),
                    "duration_ms": w.get("duration_ms"),
                    "chart_type": w.get("chart", {}).get("type") if "chart" in w else None,
                    "error": w.get("error"),
                }
                for w in widgets
            ],
        })

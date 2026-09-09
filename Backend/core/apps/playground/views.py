from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.query.models import QueryHistory
from apps.query.services import QueryExecutionError

from .metabase_client import MetabaseClient, MetabaseError
from .services import build_widget, fetch_schema_summary


class PlaygroundChatView(APIView):
    """
    One chat message -> one chart: runs the message against the lakehouse
    (Iceberg tables on MinIO, via Trino) and creates a single Metabase Card
    (in its own single-card Dashboard, for a stable embeddable link) -
    rendering happens in Metabase, not in this app.
    """

    permission_classes = [IsAuthenticated]

    # How many previous turns of the conversation to give the model as
    # context - bounded so the prompt doesn't grow without limit over a
    # long session.
    MAX_HISTORY_TURNS = 6

    def post(self, request):
        prompt = (request.data.get("prompt") or "").strip()

        if not prompt:
            return Response(
                {"error": "prompt is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_history = request.data.get("history") or []
        history = [
            {"prompt": str(turn.get("prompt", "")).strip(), "sql": str(turn.get("sql", "")).strip()}
            for turn in raw_history
            if isinstance(turn, dict) and turn.get("prompt") and turn.get("sql")
        ][-self.MAX_HISTORY_TURNS:]

        trino_user = request.user.email.split("@")[0]

        try:
            schema_summary = fetch_schema_summary(trino_user)
        except QueryExecutionError as ex:
            return Response({"error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

        widget = build_widget(trino_user, prompt, schema_summary, history=history)

        if "error" in widget:
            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=f"-- prompt: {prompt}",
                status="error",
                error_message=widget["error"],
            )
            return Response({"error": widget["error"]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            metabase = MetabaseClient()
            database_id = metabase.find_or_create_lakehouse_database_id()

            card = metabase.create_card(
                database_id=database_id,
                name=prompt[:60],
                sql=widget["sql"],
                display=metabase.chart_to_display(widget["chart"]["type"]),
            )

            dashboard = metabase.create_dashboard(name=f"AI: {prompt[:60]}")
            metabase.add_cards_to_dashboard(dashboard["id"], [card["id"]])

            try:
                embed_url = metabase.create_public_link(dashboard["id"])
            except MetabaseError:
                # Public sharing may not be turned on in Metabase yet - the
                # dashboard still exists and is reachable via dashboard_url,
                # it just can't be embedded in an iframe until an admin enables it.
                embed_url = None

        except MetabaseError as ex:
            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=f"-- prompt: {prompt}\n{widget['sql']}",
                status="error",
                error_message=str(ex),
            )
            return Response(
                {"error": f"Query ran but Metabase card creation failed: {ex}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        QueryHistory.objects.create(
            trino_user=trino_user,
            sql_text=f"-- prompt: {prompt}\n{widget['sql']}",
            status="success",
            row_count=widget["row_count"],
            duration_ms=widget["duration_ms"],
        )

        return Response({
            "prompt": prompt,
            "sql": widget["sql"],
            "row_count": widget["row_count"],
            "duration_ms": widget["duration_ms"],
            "chart_type": widget["chart"]["type"],
            "dashboard_url": metabase.dashboard_url(dashboard["id"]),
            "embed_url": embed_url,
        })

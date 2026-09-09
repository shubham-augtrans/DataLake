from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.query.models import QueryHistory
from apps.query.services import QueryExecutionError

from .metabase_client import MetabaseClient, MetabaseError
from .services import (
    COLOR_NAME_TO_HEX,
    build_chat_reply,
    build_multiple_widgets,
    build_widget,
    classify_intent,
    fetch_schema_summary,
    plan_edit,
    wants_add_chart,
    wants_multi_chart,
)

MIN_SIZE_X, MAX_SIZE_X = 4, 24
MIN_SIZE_Y, MAX_SIZE_Y = 2, 16


def _clamp(value, low, high):
    return max(low, min(high, value))


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

        previous_card_id = request.data.get("previous_card_id")
        previous_dashboard_id = request.data.get("previous_dashboard_id")
        previous_embed_url = request.data.get("previous_embed_url")
        has_previous_dashboard = bool(previous_card_id and previous_dashboard_id)
        # "add a chart for X" - append a new card to the dashboard already on
        # screen instead of replacing what's on it.
        add_to_dashboard = has_previous_dashboard and wants_add_chart(prompt)
        # Every other follow-up query replaces the one chart already on
        # screen rather than creating a new dashboard alongside it.
        reuse_dashboard = has_previous_dashboard and not add_to_dashboard

        trino_user = request.user.email.split("@")[0]

        try:
            schema_summary = fetch_schema_summary(trino_user)
        except QueryExecutionError as ex:
            return Response({"error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

        intent = classify_intent(prompt, history=history)

        if intent == "chat":
            reply = build_chat_reply(trino_user, prompt, schema_summary, history=history)

            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=f"-- prompt: {prompt}\n{reply['sql'] or '-- (no query - conversational reply)'}",
                status="success",
            )

            return Response({
                "prompt": prompt,
                "answer": reply["answer"],
                "sql": reply["sql"],
                "is_chat_only": True,
            })

        if intent == "edit":
            return self._handle_edit(
                request, prompt, history, trino_user,
                previous_card_id, previous_dashboard_id, previous_embed_url,
            )

        multi_count = wants_multi_chart(prompt)
        if multi_count and multi_count > 1:
            return self._handle_multi_chart(
                trino_user, prompt, schema_summary, multi_count, history,
                add_to_dashboard, previous_dashboard_id, previous_embed_url,
            )

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

            if add_to_dashboard:
                # New card, same dashboard - existing card(s) stay untouched.
                card = metabase.create_card(
                    database_id=database_id,
                    name=prompt[:60],
                    sql=widget["sql"],
                    display=metabase.chart_to_display(widget["chart"]["type"]),
                )
                metabase.append_card_to_dashboard(previous_dashboard_id, card["id"])

                card_id = card["id"]
                dashboard_id = previous_dashboard_id
                embed_url = previous_embed_url

            elif reuse_dashboard:
                # Replace the existing card in place instead of creating a
                # second dashboard for this turn.
                metabase.update_card(
                    card_id=previous_card_id,
                    sql=widget["sql"],
                    database_id=database_id,
                    display=metabase.chart_to_display(widget["chart"]["type"]),
                )
                card_id = previous_card_id
                dashboard_id = previous_dashboard_id
                embed_url = previous_embed_url
            else:
                card = metabase.create_card(
                    database_id=database_id,
                    name=prompt[:60],
                    sql=widget["sql"],
                    display=metabase.chart_to_display(widget["chart"]["type"]),
                )

                dashboard = metabase.create_dashboard(name=f"AI: {prompt[:60]}")
                metabase.add_cards_to_dashboard(dashboard["id"], [card["id"]])

                card_id = card["id"]
                dashboard_id = dashboard["id"]

                try:
                    embed_url = metabase.create_public_link(dashboard_id)
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
            "answer": widget["answer"],
            "sql": widget["sql"],
            "row_count": widget["row_count"],
            "duration_ms": widget["duration_ms"],
            "chart_type": widget["chart"]["type"],
            "dashboard_url": metabase.dashboard_url(dashboard_id),
            "embed_url": embed_url,
            "card_id": card_id,
            "dashboard_id": dashboard_id,
            "updated_existing": reuse_dashboard or add_to_dashboard,
            "is_chat_only": False,
        })

    def _handle_edit(
        self, request, prompt, history, trino_user,
        previous_card_id, previous_dashboard_id, previous_embed_url,
    ):
        """
        EDIT-intent turn: rename/recolor/resize/reposition a card already on
        the dashboard, or answer a question about that metadata - never
        touches the underlying data/SQL.
        """
        if not previous_dashboard_id:
            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=f"-- prompt: {prompt}\n-- (edit request, no dashboard yet)",
                status="success",
            )
            return Response({
                "prompt": prompt,
                "answer": "There's no chart on the dashboard yet to edit - ask for one first.",
                "sql": None,
                "is_chat_only": True,
            })

        try:
            metabase = MetabaseClient()
            cards_summary = metabase.get_dashboard_cards_summary(previous_dashboard_id)
        except MetabaseError as ex:
            return Response(
                {"error": f"Couldn't read the dashboard's current cards: {ex}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = plan_edit(prompt, cards_summary, history=history)
        actions = plan["actions"]

        valid_ids = {c["card_id"] for c in cards_summary}
        fallback_card_id = previous_card_id if previous_card_id in valid_ids else (
            cards_summary[0]["card_id"] if len(cards_summary) == 1 else None
        )

        layout_by_card_id = {}
        touched_card_id = None

        try:
            for action in actions:
                if not isinstance(action, dict):
                    continue

                op = action.get("op")
                card_id = action.get("card_id") or fallback_card_id
                if card_id not in valid_ids:
                    continue

                if op == "rename" and action.get("name"):
                    metabase.rename_card(card_id, str(action["name"])[:254])
                    touched_card_id = card_id

                elif op == "recolor" and action.get("color"):
                    color = str(action["color"]).strip().lower()
                    hex_color = color if color.startswith("#") else COLOR_NAME_TO_HEX.get(color)
                    if hex_color:
                        metabase.update_card_visualization_settings(
                            card_id, {"graph.colors": [hex_color]}
                        )
                        touched_card_id = card_id

                elif op == "resize":
                    entry = layout_by_card_id.setdefault(card_id, {})
                    if "size_x" in action:
                        entry["size_x"] = _clamp(int(action["size_x"]), MIN_SIZE_X, MAX_SIZE_X)
                    if "size_y" in action:
                        entry["size_y"] = _clamp(int(action["size_y"]), MIN_SIZE_Y, MAX_SIZE_Y)
                    touched_card_id = card_id

                elif op == "move":
                    entry = layout_by_card_id.setdefault(card_id, {})
                    if "row" in action:
                        entry["row"] = max(0, int(action["row"]))
                    if "col" in action:
                        entry["col"] = max(0, int(action["col"]))
                    touched_card_id = card_id

            if layout_by_card_id:
                metabase.update_dashcard_layout(previous_dashboard_id, layout_by_card_id)

        except MetabaseError as ex:
            return Response(
                {"error": f"Edit failed: {ex}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        QueryHistory.objects.create(
            trino_user=trino_user,
            sql_text=f"-- prompt: {prompt}\n-- (dashboard edit, no query)",
            status="success",
        )

        if not touched_card_id:
            # Pure question ("what's this chart called?") or nothing
            # resolvable to edit - answer only, dashboard untouched.
            return Response({
                "prompt": prompt,
                "answer": plan["answer"],
                "sql": None,
                "is_chat_only": True,
            })

        return Response({
            "prompt": prompt,
            "answer": plan["answer"],
            "sql": None,
            "is_chat_only": False,
            "updated_existing": True,
            "card_id": touched_card_id,
            "dashboard_id": previous_dashboard_id,
            "dashboard_url": metabase.dashboard_url(previous_dashboard_id),
            "embed_url": previous_embed_url,
        })

    def _handle_multi_chart(
        self, trino_user, prompt, schema_summary, count, history,
        add_to_dashboard, previous_dashboard_id, previous_embed_url,
    ):
        """
        "Create N different charts" in one message - generates up to
        `count` distinct, real (never fake/random) charts and puts them all
        on one dashboard, either the one already on screen (if the user
        also said "add") or a fresh one.
        """
        widgets = build_multiple_widgets(trino_user, prompt, schema_summary, count, history=history)

        if not widgets:
            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=f"-- prompt: {prompt}",
                status="error",
                error_message="Could not generate any charts for this request.",
            )
            return Response(
                {"error": "Couldn't generate any charts from that request - try rephrasing it."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            metabase = MetabaseClient()
            database_id = metabase.find_or_create_lakehouse_database_id()

            card_ids = [
                metabase.create_card(
                    database_id=database_id,
                    name=widget["prompt"][:60],
                    sql=widget["sql"],
                    display=metabase.chart_to_display(widget["chart"]["type"]),
                )["id"]
                for widget in widgets
            ]

            if add_to_dashboard and previous_dashboard_id:
                for card_id in card_ids:
                    metabase.append_card_to_dashboard(previous_dashboard_id, card_id)
                dashboard_id = previous_dashboard_id
                embed_url = previous_embed_url
            else:
                dashboard = metabase.create_dashboard(name=f"AI: {prompt[:60]}")
                metabase.add_cards_to_dashboard(dashboard["id"], card_ids)
                dashboard_id = dashboard["id"]

                try:
                    embed_url = metabase.create_public_link(dashboard_id)
                except MetabaseError:
                    embed_url = None

        except MetabaseError as ex:
            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=f"-- prompt: {prompt}",
                status="error",
                error_message=str(ex),
            )
            return Response(
                {"error": f"Charts ran but Metabase card creation failed: {ex}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for widget in widgets:
            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=f"-- prompt: {widget['prompt']}\n{widget['sql']}",
                status="success",
                row_count=widget["row_count"],
                duration_ms=widget["duration_ms"],
            )

        titles = "; ".join(w["prompt"] for w in widgets)
        skipped_note = (
            f" ({count - len(widgets)} question(s) couldn't be turned into a chart and were skipped.)"
            if len(widgets) < count else ""
        )
        answer = f"Created {len(widgets)} charts: {titles}.{skipped_note}"

        last = widgets[-1]

        return Response({
            "prompt": prompt,
            "answer": answer,
            "sql": last["sql"],
            "row_count": last["row_count"],
            "duration_ms": last["duration_ms"],
            "chart_type": last["chart"]["type"],
            "dashboard_url": metabase.dashboard_url(dashboard_id),
            "embed_url": embed_url,
            "card_id": card_ids[-1],
            "dashboard_id": dashboard_id,
            "updated_existing": bool(add_to_dashboard and previous_dashboard_id),
            "is_chat_only": False,
        })

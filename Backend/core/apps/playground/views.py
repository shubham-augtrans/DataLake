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
    plan_dashboard_operation,
    resolve_relative_layout,
    wants_multi_chart,
)

MIN_SIZE_X, MAX_SIZE_X = 4, 24
MIN_SIZE_Y, MAX_SIZE_Y = 2, 16


def _clamp(value, low, high):
    return max(low, min(high, value))


class PlaygroundChatView(APIView):
    """
    Chat-driven dashboard editor: each message either starts a dashboard
    (first chart) or performs one operation against the dashboard already on
    screen (create/update/delete/duplicate/move/resize/rename/recolor a
    card), planned against the dashboard's actual current state rather than
    guessed from the message in isolation - see
    services.plan_dashboard_operation for why that distinction matters.
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

        if intent == "edit" and not has_previous_dashboard:
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

        # "Create N different charts" is unambiguous bulk creation - handle
        # it before the single-operation planner either way.
        multi_count = wants_multi_chart(prompt)
        if multi_count and multi_count > 1:
            return self._handle_multi_chart(
                trino_user, prompt, schema_summary, multi_count, history,
                has_previous_dashboard, previous_dashboard_id, previous_embed_url,
            )

        if not has_previous_dashboard:
            # Nothing on screen yet - trivially a create. No dashboard state
            # to plan against, so this bootstraps via the plain chart
            # pipeline (semantics only: SQL + chart type).
            return self._create_first_chart(trino_user, prompt, schema_summary, history)

        # A dashboard already exists - every turn that could touch it
        # (create, update, delete, duplicate, move, resize, rename, recolor,
        # or a metadata question) is planned by ONE dashboard-state-aware
        # call, so "create a new chart beside it" and "change it to a pie
        # chart" - which share no distinguishing keyword - are told apart by
        # something that can actually see what's on the dashboard.
        return self._handle_dashboard_operation(
            prompt, history, trino_user, schema_summary,
            previous_card_id, previous_dashboard_id, previous_embed_url,
        )

    def _create_first_chart(self, trino_user, prompt, schema_summary, history):
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
            "card_id": card["id"],
            "dashboard_id": dashboard_id,
            "updated_existing": False,
            "is_chat_only": False,
        })

    def _handle_dashboard_operation(
        self, prompt, history, trino_user, schema_summary,
        previous_card_id, previous_dashboard_id, previous_embed_url,
    ):
        """
        Single entry point for every turn against a dashboard that already
        exists. Fetches the dashboard's real current cards, asks
        plan_dashboard_operation to decide what to do (grounded in that
        state, not just the message), validates every target card_id
        against the real card list, then executes.

        Chart SEMANTICS (SQL/chart-type, via build_widget) stay fully
        separate from dashboard LAYOUT (create/move/resize position, via
        resolve_relative_layout + MetabaseClient) - "create a new pie
        chart" and "put the pie chart beside the bar chart" go through
        different code paths even though the planner may emit both kinds of
        instruction in the same turn.
        """
        try:
            metabase = MetabaseClient()
            cards_summary = metabase.get_dashboard_cards_summary(previous_dashboard_id)
        except MetabaseError as ex:
            return Response(
                {"error": f"Couldn't read the dashboard's current cards: {ex}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = plan_dashboard_operation(prompt, cards_summary, history=history)
        actions = plan["actions"]

        valid_ids = {c["card_id"] for c in cards_summary}
        cards_by_id = {c["card_id"]: c for c in cards_summary}
        # Only used when the planner names no target and there's an
        # obvious single one - never a silent guess among several charts.
        fallback_card_id = previous_card_id if previous_card_id in valid_ids else (
            cards_summary[0]["card_id"] if len(cards_summary) == 1 else None
        )

        layout_by_card_id = {}
        touched_card_id = None
        new_widget = None
        database_id = None
        dashboard_changed = False

        try:
            for action in actions:
                if not isinstance(action, dict):
                    continue
                op = action.get("op")

                if op == "create":
                    # New card - existing cards are never touched by this
                    # branch, so "create another chart" is always additive.
                    if database_id is None:
                        database_id = metabase.find_or_create_lakehouse_database_id()

                    widget = build_widget(trino_user, prompt, schema_summary, history=history)
                    if "error" in widget:
                        continue

                    card = metabase.create_card(
                        database_id=database_id,
                        name=widget["prompt"][:60],
                        sql=widget["sql"],
                        display=metabase.chart_to_display(widget["chart"]["type"]),
                    )

                    layout = action.get("layout") or {}
                    anchor = cards_by_id.get(layout.get("relative_to"))
                    position = resolve_relative_layout(anchor, layout.get("placement"))
                    if position:
                        metabase.append_card_to_dashboard(
                            previous_dashboard_id, card["id"], row=position["row"], col=position["col"]
                        )
                    else:
                        metabase.append_card_to_dashboard(previous_dashboard_id, card["id"])

                    touched_card_id = card["id"]
                    new_widget = widget
                    dashboard_changed = True

                elif op == "update":
                    card_id = action.get("card_id") or fallback_card_id
                    if card_id not in valid_ids:
                        continue
                    if database_id is None:
                        database_id = metabase.find_or_create_lakehouse_database_id()

                    widget = build_widget(trino_user, prompt, schema_summary, history=history)
                    if "error" in widget:
                        continue

                    metabase.update_card(
                        card_id=card_id,
                        sql=widget["sql"],
                        database_id=database_id,
                        display=metabase.chart_to_display(widget["chart"]["type"]),
                    )
                    touched_card_id = card_id
                    new_widget = widget
                    dashboard_changed = True

                elif op == "delete":
                    card_id = action.get("card_id") or fallback_card_id
                    if card_id not in valid_ids:
                        continue

                    metabase.remove_card_from_dashboard(previous_dashboard_id, card_id)
                    dashboard_changed = True
                    # No single "focused" card afterwards unless one was
                    # already the fallback and survives the delete.
                    touched_card_id = fallback_card_id if fallback_card_id != card_id else None

                elif op == "duplicate":
                    card_id = action.get("card_id") or fallback_card_id
                    if card_id not in valid_ids:
                        continue
                    if database_id is None:
                        database_id = metabase.find_or_create_lakehouse_database_id()

                    # Copies the source card's exact query - never
                    # regenerated by the LLM, so the data is guaranteed
                    # identical, per "duplicate this chart" meaning exactly that.
                    new_card = metabase.duplicate_card(card_id, database_id)

                    layout = action.get("layout") or {}
                    anchor = cards_by_id.get(layout.get("relative_to")) or cards_by_id.get(card_id)
                    position = resolve_relative_layout(anchor, layout.get("placement") or "right")
                    if position:
                        metabase.append_card_to_dashboard(
                            previous_dashboard_id, new_card["id"], row=position["row"], col=position["col"]
                        )
                    else:
                        metabase.append_card_to_dashboard(previous_dashboard_id, new_card["id"])

                    touched_card_id = new_card["id"]
                    dashboard_changed = True

                elif op == "move":
                    card_id = action.get("card_id") or fallback_card_id
                    if card_id not in valid_ids:
                        continue

                    layout = action.get("layout") or {}
                    anchor = cards_by_id.get(layout.get("relative_to"))
                    position = resolve_relative_layout(anchor, layout.get("placement"))
                    if position:
                        layout_by_card_id.setdefault(card_id, {}).update(position)
                        touched_card_id = card_id
                        dashboard_changed = True

                elif op == "resize":
                    card_id = action.get("card_id") or fallback_card_id
                    if card_id not in valid_ids:
                        continue

                    entry = layout_by_card_id.setdefault(card_id, {})
                    if "size_x" in action:
                        entry["size_x"] = _clamp(int(action["size_x"]), MIN_SIZE_X, MAX_SIZE_X)
                    if "size_y" in action:
                        entry["size_y"] = _clamp(int(action["size_y"]), MIN_SIZE_Y, MAX_SIZE_Y)
                    touched_card_id = card_id
                    dashboard_changed = True

                elif op == "rename":
                    card_id = action.get("card_id") or fallback_card_id
                    if card_id not in valid_ids or not action.get("name"):
                        continue

                    metabase.rename_card(card_id, str(action["name"])[:254])
                    touched_card_id = card_id
                    dashboard_changed = True

                elif op == "recolor":
                    card_id = action.get("card_id") or fallback_card_id
                    if card_id not in valid_ids or not action.get("color"):
                        continue

                    color = str(action["color"]).strip().lower()
                    hex_color = color if color.startswith("#") else COLOR_NAME_TO_HEX.get(color)
                    if hex_color:
                        metabase.update_card_visualization_settings(card_id, {"graph.colors": [hex_color]})
                        touched_card_id = card_id
                        dashboard_changed = True

            if layout_by_card_id:
                metabase.update_dashcard_layout(previous_dashboard_id, layout_by_card_id)

        except MetabaseError as ex:
            return Response(
                {"error": f"Dashboard operation failed: {ex}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_widget:
            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=f"-- prompt: {prompt}\n{new_widget['sql']}",
                status="success",
                row_count=new_widget["row_count"],
                duration_ms=new_widget["duration_ms"],
            )
        else:
            QueryHistory.objects.create(
                trino_user=trino_user,
                sql_text=f"-- prompt: {prompt}\n-- (dashboard operation, no query)",
                status="success",
            )

        if not dashboard_changed:
            # Pure question ("what's this chart called?") or a request the
            # planner couldn't confidently resolve to a target - answer
            # only, dashboard untouched (never guess-mutate an ambiguous
            # reference).
            return Response({
                "prompt": prompt,
                "answer": plan["answer"],
                "sql": None,
                "is_chat_only": True,
            })

        return Response({
            "prompt": prompt,
            "answer": plan["answer"],
            "sql": new_widget["sql"] if new_widget else None,
            "row_count": new_widget["row_count"] if new_widget else None,
            "duration_ms": new_widget["duration_ms"] if new_widget else None,
            "chart_type": new_widget["chart"]["type"] if new_widget else None,
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
        on one dashboard, either the one already on screen (if one exists)
        or a fresh one.
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

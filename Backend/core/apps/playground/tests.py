"""
Tests for the dashboard-operation architecture in views.py/services.py.

External systems (Trino, the hosted LLM, Metabase) are mocked throughout -
these tests are about the DECISION/VALIDATION/EXECUTION layer this change
introduced (services.plan_dashboard_operation's parsing, and
views.PlaygroundChatView's dispatch + card_id validation), not about
whether a real LLM makes the "right" call for a given sentence. The real
model's actual behavior for the scenarios in the task description was
verified live against the running stack (see chat history / PR notes),
not here.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.playground.metabase_client import DEFAULT_SIZE_X, DEFAULT_SIZE_Y
from apps.playground.services import (
    _extract_json,
    plan_dashboard_operation,
    resolve_relative_layout,
)
from apps.playground.views import PlaygroundChatView

User = get_user_model()


# ---------------------------------------------------------------------------
# Pure helper functions - no mocking needed.
# ---------------------------------------------------------------------------

class ResolveRelativeLayoutTests(TestCase):
    def setUp(self):
        self.anchor = {"row": 0, "col": 0, "size_x": DEFAULT_SIZE_X, "size_y": DEFAULT_SIZE_Y}

    def test_beside_and_right_place_to_the_right_of_anchor(self):
        for placement in ("right", "beside"):
            result = resolve_relative_layout(self.anchor, placement)
            self.assertEqual(result, {"row": 0, "col": DEFAULT_SIZE_X})

    def test_left_places_before_anchor(self):
        anchor = {"row": 0, "col": DEFAULT_SIZE_X, "size_x": DEFAULT_SIZE_X, "size_y": DEFAULT_SIZE_Y}
        result = resolve_relative_layout(anchor, "left")
        self.assertEqual(result, {"row": 0, "col": 0})

    def test_left_clamps_at_zero(self):
        result = resolve_relative_layout(self.anchor, "left")
        self.assertEqual(result["col"], 0)

    def test_below_places_under_anchor(self):
        result = resolve_relative_layout(self.anchor, "below")
        self.assertEqual(result, {"row": DEFAULT_SIZE_Y, "col": 0})

    def test_above_clamps_at_zero(self):
        result = resolve_relative_layout(self.anchor, "above")
        self.assertEqual(result["row"], 0)

    def test_no_anchor_returns_none(self):
        self.assertIsNone(resolve_relative_layout(None, "right"))

    def test_no_placement_returns_none(self):
        self.assertIsNone(resolve_relative_layout(self.anchor, None))

    def test_unknown_placement_returns_none(self):
        self.assertIsNone(resolve_relative_layout(self.anchor, "diagonally"))


class ExtractJsonTests(TestCase):
    def test_plain_json(self):
        self.assertEqual(_extract_json('{"a": 1}'), {"a": 1})

    def test_json_in_markdown_fence(self):
        self.assertEqual(_extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_json_with_surrounding_prose(self):
        self.assertEqual(_extract_json('Sure, here you go:\n{"a": 1}\nHope that helps!'), {"a": 1})

    def test_garbage_returns_none(self):
        self.assertIsNone(_extract_json("not json at all"))


# ---------------------------------------------------------------------------
# plan_dashboard_operation - the LLM call is mocked; this tests the
# parsing/fallback contract the executor (views.py) relies on.
# ---------------------------------------------------------------------------

class PlanDashboardOperationTests(TestCase):
    def test_no_cards_bootstraps_to_create(self):
        plan = plan_dashboard_operation("create a bar chart", cards_summary=[])
        self.assertEqual(plan["actions"], [{"op": "create", "layout": {}}])

    @patch("apps.playground.services._call_llm")
    def test_valid_json_response_is_parsed(self, mock_call_llm):
        mock_call_llm.return_value = (
            '{"actions": [{"op": "create", "layout": {"relative_to": 2, "placement": "right"}}], '
            '"answer": "Adding a new chart beside it."}'
        )
        cards = [{"card_id": 2, "name": "Sales by Category", "display": "pie",
                  "row": 0, "col": 0, "size_x": 12, "size_y": 8}]
        plan = plan_dashboard_operation("create a new chart beside it", cards)
        self.assertEqual(plan["actions"][0]["op"], "create")
        self.assertEqual(plan["actions"][0]["layout"]["relative_to"], 2)
        self.assertEqual(plan["actions"][0]["layout"]["placement"], "right")

    @patch("apps.playground.services._call_llm")
    def test_unparseable_response_falls_back_to_empty_actions(self, mock_call_llm):
        mock_call_llm.return_value = "I'm not sure what you mean."
        cards = [{"card_id": 1, "name": "X", "display": "bar", "row": 0, "col": 0, "size_x": 12, "size_y": 8}]
        plan = plan_dashboard_operation("do the thing", cards)
        self.assertEqual(plan["actions"], [])
        self.assertTrue(plan["answer"])


# ---------------------------------------------------------------------------
# End-to-end view dispatch, with Metabase/Trino/LLM boundaries mocked.
# ---------------------------------------------------------------------------

def _card(card_id, name, display, row, col, size_x=12, size_y=8):
    return {"card_id": card_id, "name": name, "display": display,
            "row": row, "col": col, "size_x": size_x, "size_y": size_y}


def _widget(prompt, chart_type="bar", sql="SELECT 1"):
    return {
        "prompt": prompt, "sql": sql, "columns": ["a"], "rows": [[1]],
        "row_count": 1, "truncated": False, "duration_ms": 10,
        "chart": {"type": chart_type, "x_field": "a", "y_field": "a"},
        "answer": f"Answer for {prompt}",
    }


class DashboardOperationViewTests(TestCase):
    """
    Drives PlaygroundChatView.post() directly. MetabaseClient is patched at
    the views module so no real HTTP call happens; build_widget/
    classify_intent/plan_dashboard_operation are patched per-test to make
    the LLM's decision deterministic while exercising the real dispatch,
    validation, and MetabaseClient-call wiring this change is actually about.
    """

    def setUp(self):
        self.user = User.objects.create_user(email="tester@example.com", password="x")
        self.factory = APIRequestFactory()

    def _post(self, payload):
        request = self.factory.post("/api/playground/chat/", payload, format="json")
        force_authenticate(request, user=self.user)
        return PlaygroundChatView.as_view()(request)

    def _mock_metabase(self, mock_cls, cards_summary=None):
        instance = MagicMock()
        mock_cls.return_value = instance
        instance.find_or_create_lakehouse_database_id.return_value = 1
        instance.get_dashboard_cards_summary.return_value = cards_summary or []
        instance.create_card.side_effect = lambda **kw: {"id": 100 + instance.create_card.call_count}
        instance.create_dashboard.return_value = {"id": 999}
        instance.create_public_link.return_value = "http://mb/public/x"
        instance.dashboard_url.side_effect = lambda did: f"http://mb/dashboard/{did}"
        instance.chart_to_display.side_effect = lambda t: t
        return instance

    # -- Create first chart ------------------------------------------------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="chart")
    @patch("apps.playground.views.build_widget")
    @patch("apps.playground.views.MetabaseClient")
    def test_create_first_chart(self, mock_cls, mock_build_widget, mock_intent, mock_schema):
        mb = self._mock_metabase(mock_cls)
        mock_build_widget.return_value = _widget("sales by region", "bar")

        response = self._post({"prompt": "Create a bar chart showing sales by region.", "history": []})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_chat_only"])
        self.assertFalse(response.data["updated_existing"])
        mb.create_card.assert_called_once()
        mb.create_dashboard.assert_called_once()

    # -- Create second/another chart (the reported bug) ---------------------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="chart")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.build_widget")
    @patch("apps.playground.views.MetabaseClient")
    def test_create_beside_existing_chart_adds_third_without_touching_others(
        self, mock_cls, mock_build_widget, mock_plan, mock_intent, mock_schema
    ):
        cards = [
            _card(1, "Sales by Region", "bar", row=0, col=0),
            _card(2, "Sales by Category", "pie", row=0, col=12),
        ]
        mb = self._mock_metabase(mock_cls, cards_summary=cards)
        mock_build_widget.return_value = _widget("a third chart", "line")
        mock_plan.return_value = {
            "actions": [{"op": "create", "layout": {"relative_to": 2, "placement": "right"}}],
            "answer": "Added a new chart beside the pie chart.",
        }

        response = self._post({
            "prompt": "Create a new chart beside it.", "history": [],
            "previous_card_id": 2, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_chat_only"])
        # A NEW card was created - existing cards 1 and 2 were never
        # updated or removed. This is the exact bug: the old code would
        # have called update_card(card_id=2, ...) here instead.
        mb.create_card.assert_called_once()
        mb.update_card.assert_not_called()
        mb.remove_card_from_dashboard.assert_not_called()
        # Positioned beside card 2 (row=0, col=2's col + 2's size_x=12 -> col=24)
        mb.append_card_to_dashboard.assert_called_once()
        _, kwargs = mb.append_card_to_dashboard.call_args
        self.assertEqual(kwargs["row"], 0)
        self.assertEqual(kwargs["col"], 24)

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="chart")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.build_widget")
    @patch("apps.playground.views.MetabaseClient")
    def test_add_another_chart_is_additive(
        self, mock_cls, mock_build_widget, mock_plan, mock_intent, mock_schema
    ):
        cards = [_card(1, "Sales by Region", "bar", row=0, col=0)]
        mb = self._mock_metabase(mock_cls, cards_summary=cards)
        mock_build_widget.return_value = _widget("another chart", "bar")
        mock_plan.return_value = {"actions": [{"op": "create", "layout": {}}], "answer": "Added another chart."}

        response = self._post({
            "prompt": "Add another chart.", "history": [],
            "previous_card_id": 1, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        mb.create_card.assert_called_once()
        mb.update_card.assert_not_called()

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="chart")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.build_widget")
    @patch("apps.playground.views.MetabaseClient")
    def test_create_below_existing_chart(self, mock_cls, mock_build_widget, mock_plan, mock_intent, mock_schema):
        cards = [_card(1, "Sales by Region", "bar", row=0, col=0)]
        mb = self._mock_metabase(mock_cls, cards_summary=cards)
        mock_build_widget.return_value = _widget("a chart below", "table")
        mock_plan.return_value = {
            "actions": [{"op": "create", "layout": {"relative_to": 1, "placement": "below"}}],
            "answer": "Added a chart below the bar chart.",
        }

        response = self._post({
            "prompt": "Add a pie chart below the existing chart.", "history": [],
            "previous_card_id": 1, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        _, kwargs = mb.append_card_to_dashboard.call_args
        self.assertEqual(kwargs["row"], 8)
        self.assertEqual(kwargs["col"], 0)

    # -- Modify (update) existing chart -------------------------------------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="chart")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.build_widget")
    @patch("apps.playground.views.MetabaseClient")
    def test_change_it_to_a_pie_chart_updates_in_place(
        self, mock_cls, mock_build_widget, mock_plan, mock_intent, mock_schema
    ):
        cards = [_card(1, "Sales by Region", "bar", row=0, col=0)]
        mb = self._mock_metabase(mock_cls, cards_summary=cards)
        mock_build_widget.return_value = _widget("sales by region", "pie")
        mock_plan.return_value = {"actions": [{"op": "update", "card_id": 1}], "answer": "Changed it to a pie chart."}

        response = self._post({
            "prompt": "Change it to a pie chart.", "history": [],
            "previous_card_id": 1, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["card_id"], 1)
        mb.update_card.assert_called_once()
        self.assertEqual(mb.update_card.call_args.kwargs["card_id"], 1)
        mb.create_card.assert_not_called()

    # -- Delete ---------------------------------------------------------------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="edit")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.MetabaseClient")
    def test_delete_existing_chart(self, mock_cls, mock_plan, mock_intent, mock_schema):
        cards = [
            _card(1, "Sales by Region", "bar", row=0, col=0),
            _card(2, "Sales by Category", "pie", row=0, col=12),
        ]
        mb = self._mock_metabase(mock_cls, cards_summary=cards)
        mock_plan.return_value = {"actions": [{"op": "delete", "card_id": 2}], "answer": "Deleted the pie chart."}

        response = self._post({
            "prompt": "Delete the pie chart.", "history": [],
            "previous_card_id": 2, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        mb.remove_card_from_dashboard.assert_called_once_with(55, 2)

    # -- Move -------------------------------------------------------------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="edit")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.MetabaseClient")
    def test_move_second_chart_below_first(self, mock_cls, mock_plan, mock_intent, mock_schema):
        cards = [
            _card(1, "Sales by Region", "bar", row=0, col=0),
            _card(2, "Another chart", "bar", row=0, col=12),
        ]
        mb = self._mock_metabase(mock_cls, cards_summary=cards)
        mock_plan.return_value = {
            "actions": [{"op": "move", "card_id": 2, "layout": {"relative_to": 1, "placement": "below"}}],
            "answer": "Moved it below the first chart.",
        }

        response = self._post({
            "prompt": "Move the second chart below the first one.", "history": [],
            "previous_card_id": 2, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        mb.update_dashcard_layout.assert_called_once()
        layout = mb.update_dashcard_layout.call_args[0][1]
        self.assertEqual(layout[2]["row"], 8)
        self.assertEqual(layout[2]["col"], 0)

    # -- Resize -----------------------------------------------------------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="edit")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.MetabaseClient")
    def test_resize_existing_chart(self, mock_cls, mock_plan, mock_intent, mock_schema):
        cards = [_card(1, "Sales by Region", "bar", row=0, col=0)]
        mb = self._mock_metabase(mock_cls, cards_summary=cards)
        mock_plan.return_value = {
            "actions": [{"op": "resize", "card_id": 1, "size_x": 20, "size_y": 8}],
            "answer": "Made it wider.",
        }

        response = self._post({
            "prompt": "Make the bar chart wider.", "history": [],
            "previous_card_id": 1, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        layout = mb.update_dashcard_layout.call_args[0][1]
        self.assertEqual(layout[1]["size_x"], 20)

    def test_resize_out_of_range_is_clamped(self):
        from apps.playground.views import _clamp
        self.assertEqual(_clamp(999, 4, 24), 24)
        self.assertEqual(_clamp(-5, 4, 24), 4)

    # -- Duplicate ----------------------------------------------------------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="edit")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.MetabaseClient")
    def test_duplicate_existing_chart_does_not_regenerate_sql(self, mock_cls, mock_plan, mock_intent, mock_schema):
        cards = [_card(1, "Sales by Region", "bar", row=0, col=0)]
        mb = self._mock_metabase(mock_cls, cards_summary=cards)
        mb.duplicate_card.return_value = {"id": 500}
        mock_plan.return_value = {
            "actions": [{"op": "duplicate", "card_id": 1, "layout": {}}],
            "answer": "Duplicated it.",
        }

        response = self._post({
            "prompt": "Duplicate this chart.", "history": [],
            "previous_card_id": 1, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        mb.duplicate_card.assert_called_once_with(1, 1)
        self.assertEqual(response.data["card_id"], 500)

    # -- Ambiguity: never guess-mutate -----------------------------------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="edit")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.MetabaseClient")
    def test_ambiguous_reference_asks_instead_of_guessing(self, mock_cls, mock_plan, mock_intent, mock_schema):
        cards = [
            _card(1, "Sales by Region", "bar", row=0, col=0),
            _card(2, "Sales by Category", "pie", row=0, col=12),
        ]
        mb = self._mock_metabase(mock_cls, cards_summary=cards)
        mock_plan.return_value = {
            "actions": [],
            "answer": "Which chart do you mean - the bar chart or the pie chart?",
        }

        response = self._post({
            "prompt": "Change the chart.", "history": [],
            "previous_card_id": None, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_chat_only"])
        mb.update_card.assert_not_called()
        mb.create_card.assert_not_called()
        mb.remove_card_from_dashboard.assert_not_called()

    # -- Edit with no dashboard yet -----------------------------------------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="edit")
    def test_edit_before_any_chart_exists_does_not_crash(self, mock_intent, mock_schema):
        response = self._post({"prompt": "Make it bigger.", "history": []})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_chat_only"])

    # -- Multi-turn conversation scenarios from the task description --------

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="chart")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.build_widget")
    @patch("apps.playground.views.MetabaseClient")
    def test_full_conversation_bar_then_pie_then_beside_it_makes_three_charts(
        self, mock_cls, mock_build_widget, mock_plan, mock_intent, mock_schema
    ):
        mb = MagicMock()
        mock_cls.return_value = mb
        mb.find_or_create_lakehouse_database_id.return_value = 1
        mb.create_dashboard.return_value = {"id": 55}
        mb.create_public_link.return_value = "http://mb/e"
        mb.dashboard_url.side_effect = lambda did: f"http://mb/dashboard/{did}"
        mb.chart_to_display.side_effect = lambda t: t

        created_ids = iter([1, 2, 3])
        mb.create_card.side_effect = lambda **kw: {"id": next(created_ids)}

        dashboard_cards = []

        def fake_add_cards(dashboard_id, card_ids):
            for i, cid in enumerate(card_ids):
                dashboard_cards.append({"card_id": cid, "row": 0, "col": i * 12, "size_x": 12, "size_y": 8})
        mb.add_cards_to_dashboard.side_effect = fake_add_cards

        def fake_append(dashboard_id, card_id, row=None, col=None):
            if row is None:
                row, col = 0, len(dashboard_cards) * 12
            dashboard_cards.append({"card_id": card_id, "row": row, "col": col, "size_x": 12, "size_y": 8})
        mb.append_card_to_dashboard.side_effect = fake_append

        mb.get_dashboard_cards_summary.side_effect = lambda did: [
            {**c, "name": f"card {c['card_id']}", "display": "bar"} for c in dashboard_cards
        ]

        # Turn 1: bar chart, sales by region -> first chart, no prior dashboard.
        mock_build_widget.return_value = _widget("sales by region", "bar")
        r1 = self._post({"prompt": "Create a bar chart showing sales by region.", "history": []})
        self.assertEqual(r1.status_code, 200)
        self.assertFalse(r1.data["updated_existing"])
        dash_id, card1 = r1.data["dashboard_id"], r1.data["card_id"]
        self.assertEqual(len(dashboard_cards), 1)

        # Turn 2: pie chart, sales by category -> second chart, dashboard exists.
        mock_build_widget.return_value = _widget("sales by category", "pie")
        mock_plan.return_value = {"actions": [{"op": "create", "layout": {}}], "answer": "Created a pie chart."}
        r2 = self._post({
            "prompt": "Create a pie chart showing sales by category.", "history": [],
            "previous_card_id": card1, "previous_dashboard_id": dash_id, "previous_embed_url": "http://mb/e",
        })
        self.assertEqual(r2.status_code, 200)
        card2 = r2.data["card_id"]
        self.assertEqual(len(dashboard_cards), 2)
        self.assertNotEqual(card2, card1)

        # Turn 3: "create a new chart beside it" - "it" = the pie chart (card2).
        mock_build_widget.return_value = _widget("beside it chart", "table")
        mock_plan.return_value = {
            "actions": [{"op": "create", "layout": {"relative_to": card2, "placement": "right"}}],
            "answer": "Created a third chart beside the pie chart.",
        }
        r3 = self._post({
            "prompt": "Create a new chart beside it.", "history": [],
            "previous_card_id": card2, "previous_dashboard_id": dash_id, "previous_embed_url": "http://mb/e",
        })
        self.assertEqual(r3.status_code, 200)
        card3 = r3.data["card_id"]

        # THE CORE ASSERTION: 3 distinct charts exist, none overwritten.
        self.assertEqual(len(dashboard_cards), 3)
        self.assertEqual({c["card_id"] for c in dashboard_cards}, {card1, card2, card3})
        mb.update_card.assert_not_called()

        # Third chart is positioned beside (to the right of) card2.
        card2_entry = next(c for c in dashboard_cards if c["card_id"] == card2)
        card3_entry = next(c for c in dashboard_cards if c["card_id"] == card3)
        self.assertEqual(card3_entry["row"], card2_entry["row"])
        self.assertEqual(card3_entry["col"], card2_entry["col"] + card2_entry["size_x"])

    @patch("apps.playground.views.fetch_schema_summary", return_value="t(a int)")
    @patch("apps.playground.views.classify_intent", return_value="chart")
    @patch("apps.playground.views.plan_dashboard_operation")
    @patch("apps.playground.views.build_widget")
    @patch("apps.playground.views.MetabaseClient")
    def test_bar_then_change_it_to_pie_leaves_one_chart(
        self, mock_cls, mock_build_widget, mock_plan, mock_intent, mock_schema
    ):
        mb = self._mock_metabase(mock_cls, cards_summary=[_card(1, "Sales", "bar", 0, 0)])
        mock_build_widget.return_value = _widget("sales", "pie")
        mock_plan.return_value = {"actions": [{"op": "update", "card_id": 1}], "answer": "Changed to pie."}

        response = self._post({
            "prompt": "Change it to a pie chart.", "history": [],
            "previous_card_id": 1, "previous_dashboard_id": 55, "previous_embed_url": "http://mb/e",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["card_id"], 1)
        self.assertEqual(response.data["chart_type"], "pie")
        mb.create_card.assert_not_called()
        mb.update_card.assert_called_once()

import json
import os
import re
import tempfile
from decimal import Decimal

import requests
from django.conf import settings

from apps.llm_models.models import LLMModel
from apps.query.services import LAKEHOUSE_SCHEMA, QueryExecutionError, TrinoQueryRunner

LLM_TIMEOUT = 60
BLOCKED_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter",
    "truncate", "grant", "revoke", "create", "replace",
)

# Explicit chart-type requests in the user's own words win over the
# deterministic shape-based inference in infer_chart() - checked longest
# phrase first so "pie chart" matches before a bare "pie" would.
CHART_TYPE_KEYWORDS = [
    ("pie chart", "pie"),
    ("pie", "pie"),
    ("bar chart", "bar"),
    ("bar graph", "bar"),
    ("bar", "bar"),
    ("line chart", "line"),
    ("line graph", "line"),
    ("trend line", "line"),
    ("table", "table"),
    ("single number", "number"),
    ("scalar", "number"),
]

# Phrases that mean "don't run a new query, just re-render the last one" -
# e.g. "same data" / "same info" as a pie chart instead.
SAME_DATA_PHRASES = ("same data", "same info", "same result", "that data", "this data")

# Phrases that mean "put this alongside what's already on the dashboard"
# rather than replace it - checked longest phrase first isn't needed here
# since these are single-purpose triggers, not overlapping like chart types.
ADD_CHART_PHRASES = (
    "add a chart", "add another chart", "add this chart", "add a new chart",
    "add another graph", "add this graph",
    "also show", "also add", "also plot", "also include",
    "add it to the dashboard", "add this to the dashboard",
    "add that to the dashboard", "on the same dashboard",
    "in the same dashboard", "alongside", "add a graph for", "add a chart for",
)


class PromptToSqlError(Exception):
    pass


def fetch_schema_summary(trino_user, max_tables=15, max_columns_per_table=20):
    """
    Compact "table(col type, col type, ...)" schema listing for the
    lakehouse's `ingested` schema (Iceberg tables on MinIO, queried through
    Trino), used as grounding context for the LLM prompt.
    """
    runner = TrinoQueryRunner(trino_user, schema=LAKEHOUSE_SCHEMA)

    tables = runner.list_tables(settings.TRINO_CATALOG, LAKEHOUSE_SCHEMA)

    lines = []
    for table in tables[:max_tables]:
        columns = runner.list_columns(settings.TRINO_CATALOG, LAKEHOUSE_SCHEMA, table)
        column_descriptions = [
            f"{column['name']} {column['type']}"
            for column in columns[:max_columns_per_table]
        ]
        lines.append(f"{table}({', '.join(column_descriptions)})")

    return "\n".join(lines)


def detect_requested_chart_type(prompt):
    """
    Returns the chart type the user explicitly asked for ("...as a pie
    chart"), or None if they didn't name one - in which case infer_chart()'s
    shape-based guess is used instead.
    """
    lowered = prompt.lower()

    for phrase, chart_type in CHART_TYPE_KEYWORDS:
        if phrase in lowered:
            return chart_type

    return None


def wants_same_data(prompt):
    """
    True if the message is asking to re-render the previous result
    (e.g. "give same data in a pie chart") rather than ask a new question -
    in which case the last turn's SQL is reused verbatim instead of asking
    the model to regenerate it, which is both faster and guarantees the
    data is actually the same.
    """
    lowered = prompt.lower()
    return any(phrase in lowered for phrase in SAME_DATA_PHRASES)


def wants_add_chart(prompt):
    """
    True if the message asks for a new chart to be added to the dashboard
    already on screen, alongside the existing one(s) - e.g. "add a chart for
    total readings per machine" - rather than replace what's there.
    """
    lowered = prompt.lower()
    return any(phrase in lowered for phrase in ADD_CHART_PHRASES)


# Common color names -> the hex Metabase's chart palette actually understands.
COLOR_NAME_TO_HEX = {
    "red": "#EF4444", "blue": "#509EE3", "green": "#84BB4C",
    "orange": "#F9AB00", "purple": "#A989C5", "yellow": "#F9D45C",
    "pink": "#F783AC", "teal": "#52C5D0", "gray": "#949AAB", "grey": "#949AAB",
    "black": "#2E353B", "cyan": "#22D3EE", "magenta": "#D946EF",
    "brown": "#92400E", "indigo": "#6366F1", "lime": "#84CC16",
}

# Checked BEFORE the chart-intent keywords below, because a message like
# "rename this chart to X" contains the word "chart" and would otherwise be
# misread as a request to build/change a new chart.
EDIT_INTENT_KEYWORDS = (
    "rename",
    "set the title", "set the name", "set the chart name", "set the card name",
    "recolor", "recolour",
    "resize", "bigger", "smaller", "larger", "wider", "taller", "shrink",
    "move it", "reposition", "move the", "put it in row", "put it in the",
    "first row", "second row", "third row", "row 1", "row 2", "row 3",
    "left side", "right side",
)

# A chart-referring word ("chart"/"card"/"graph"/"dashboard", or a bare
# "it"/"this"/"that") paired ANYWHERE in the message with a naming/coloring
# word ("call[ed]", "name", "title", "color/colour") means the message is
# about that chart's metadata, not its data - e.g. "what is the pressure
# chart called?", "what's the name of this chart?", "make this chart red".
# Checked as co-occurrence (not a fixed phrase) so it survives whatever's
# in between (the chart's topic, "the", "of", etc).
_CHART_REF = r"(?:chart|card|graph|dashboard|\bit\b|\bthis\b|\bthat\b)"
_NAME_OR_COLOR_WORD = r"(?:call(?:ed)?|name|title|colou?r)"
EDIT_COOCCURRENCE_PATTERN = re.compile(
    rf"{_CHART_REF}.*{_NAME_OR_COLOR_WORD}|{_NAME_OR_COLOR_WORD}.*{_CHART_REF}"
)

COLOR_VERB_PATTERN = re.compile(r"\b(make|turn|color|colour|set)\b")


def _looks_like_edit_request(prompt):
    lowered = prompt.lower()
    if any(keyword in lowered for keyword in EDIT_INTENT_KEYWORDS):
        return True

    if EDIT_COOCCURRENCE_PATTERN.search(lowered):
        return True

    # Catches "make the temperature chart green", "turn it blue", etc. - not
    # just the narrow "make it <color>" phrasing, since the target is often
    # named ("the temperature chart") rather than "it".
    if COLOR_VERB_PATTERN.search(lowered):
        return any(
            re.search(rf"\b{re.escape(color)}\b", lowered) for color in COLOR_NAME_TO_HEX
        )

    return False


CHART_INTENT_KEYWORDS = (
    "show", "plot", "chart", "graph", "dashboard", "visualiz", "visualis",
    "display", "draw", "build", "trend", "compare", "breakdown", "break down",
    "pie", "bar", "line", "table", "add", "change it", "make it", "switch",
    "same data", "same info",
)


def _looks_like_chart_request(prompt):
    """
    Cheap first pass before spending an LLM call on classification - if the
    message obviously wants a visualization, skip straight to CHART.
    """
    lowered = prompt.lower()
    return any(keyword in lowered for keyword in CHART_INTENT_KEYWORDS)


def classify_intent(prompt, history=None):
    """
    Decides how this chat turn should be handled:
    CHART - build a new chart or change what data/chart-type is shown
    (creates or replaces a dashboard card).
    EDIT - change a property of a chart already on the dashboard (its name,
    color, size, or position) without touching its data, or a cross-question
    about that metadata ("what's this chart called?").
    CHAT - anything else - a data question that doesn't need the dashboard
    touched at all.
    """
    if _looks_like_edit_request(prompt):
        return "edit"

    if _looks_like_chart_request(prompt):
        return "chart"

    history_block = ""
    if history:
        numbered = "\n".join(
            f"{i + 1}. {turn['prompt']}" for i, turn in enumerate(history)
        )
        history_block = f"Conversation so far (oldest first):\n{numbered}\n\n"

    system_prompt = (
        "Classify the user's latest message into exactly one category:\n"
        "CHART - they want to see, build, or change what data/chart-type is "
        "shown (e.g. 'show sales by region', 'plot temperature over time', "
        "'make it a pie chart', 'now break it down by machine').\n"
        "EDIT - they want to change a chart's name, color, size, or position "
        "on the dashboard - not its data (e.g. 'rename this to Sales', "
        "'make it blue', 'make it bigger', 'move it to the first row'), or "
        "they're asking about that metadata ('what's this chart called?').\n"
        "CHAT - a data question or cross-question that doesn't require "
        "changing anything on screen (e.g. 'why is that number so high?', "
        "'which machine has the most readings?', 'thanks').\n"
        "Respond with exactly one word: CHART, EDIT, or CHAT.\n\n"
        f"{history_block}"
        f"Message: {prompt}\n\n"
        "Answer:"
    )

    try:
        raw = _call_llm(system_prompt).strip().upper()
    except PromptToSqlError:
        # Can't reach the LLM to classify - default to the safer, cheaper
        # path (chat-only) rather than silently mutating the dashboard.
        return "chat"

    if "EDIT" in raw:
        return "edit"
    if "CHART" in raw:
        return "chart"
    return "chat"


def _extract_json(raw_text):
    """
    Pull a single JSON object out of whatever the model returned - same
    reasoning as _extract_sql: small models routinely wrap it in prose or
    markdown fences.
    """
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else raw_text

    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def plan_edit(prompt, cards_summary, history=None):
    """
    Turns an EDIT-intent message into a structured plan the caller can
    execute against the Metabase API: which card(s) to rename/recolor/
    resize/reposition, and/or a direct answer if it was just a question
    about the dashboard's current state (e.g. "what's this chart called?").

    Returns {"actions": [...], "answer": "..."} - actions is empty for a
    pure question. Never raises - a plan the caller can't make sense of
    comes back with empty actions and the model's raw reply as the answer,
    same fallback shape as a successful "just answer" response.
    """
    if not cards_summary:
        return {
            "actions": [],
            "answer": "There's no chart on the dashboard yet to edit - ask for one first.",
        }

    cards_block = "\n".join(
        f"{i + 1}. card_id={c['card_id']} name=\"{c['name']}\" display={c['display']} "
        f"row={c['row']} col={c['col']} size_x={c['size_x']} size_y={c['size_y']}"
        for i, c in enumerate(cards_summary)
    )

    history_block = ""
    if history:
        numbered = "\n".join(
            f"{i + 1}. {turn['prompt']}" for i, turn in enumerate(history)
        )
        history_block = f"Conversation so far (oldest first):\n{numbered}\n\n"

    system_prompt = (
        "You manage the layout and labeling of charts on a dashboard. Given "
        "the user's message and the charts currently on it, respond with "
        "ONLY a single JSON object (no prose, no markdown fences) matching "
        "this shape:\n"
        '{"actions": [\n'
        '  {"op": "rename", "card_id": <int|null>, "name": "<new title>"},\n'
        '  {"op": "recolor", "card_id": <int|null>, "color": "<color word or hex>"},\n'
        '  {"op": "resize", "card_id": <int|null>, "size_x": <int 4-24>, "size_y": <int 2-16>},\n'
        '  {"op": "move", "card_id": <int|null>, "row": <int>, "col": <int>}\n'
        '], "answer": "<short natural reply>"}\n\n'
        "Rules:\n"
        "- card_id must be one of the card_id values listed below, or null "
        "if the user didn't name a specific chart and there's an obvious "
        "single target (e.g. only one chart exists, or they said 'it'/'this').\n"
        "- The dashboard grid is 24 columns wide. The standard card size is "
        "size_x=12 size_y=8, so two cards fit side by side per row (col=0 "
        "and col=12). A new row N (1-indexed) starts at row=(N-1)*8.\n"
        "- If the user names a chart by its topic (e.g. 'the pressure "
        "chart'), match it to the closest name in the list.\n"
        "- If the user is only asking a question and nothing needs to "
        "change, return an empty actions array and put the answer in "
        "'answer'.\n"
        "- Always fill 'answer' with a short, natural confirmation of what "
        "you did (or the answer to their question).\n\n"
        f"Charts currently on the dashboard:\n{cards_block}\n\n"
        f"{history_block}"
        f"Message: {prompt}\n\n"
        "JSON:"
    )

    try:
        raw_text = _call_llm(system_prompt)
    except PromptToSqlError:
        return {
            "actions": [],
            "answer": "Couldn't reach the model to plan that edit - try again in a moment.",
        }

    parsed = _extract_json(raw_text)
    if not isinstance(parsed, dict) or "actions" not in parsed:
        return {"actions": [], "answer": raw_text.strip() or "Sorry, I couldn't figure out that edit."}

    actions = parsed.get("actions") or []
    if not isinstance(actions, list):
        actions = []

    return {
        "actions": actions,
        "answer": str(parsed.get("answer") or "Done.").strip(),
    }


def free_chat_answer(prompt, history=None):
    """
    Conversational fallback for a CHAT-intent message that isn't really a
    data question at all ("thanks", "what did I just ask you") - no SQL, no
    schema, just the conversation so far.
    """
    history_block = ""
    if history:
        numbered = "\n".join(
            f"{i + 1}. {turn['prompt']}" for i, turn in enumerate(history)
        )
        history_block = f"Conversation so far (oldest first):\n{numbered}\n\n"

    system_prompt = (
        "You are a helpful data analyst assistant chatting with a user about "
        "their lakehouse data. Reply conversationally in 1-3 short sentences.\n\n"
        f"{history_block}"
        f"Message: {prompt}\n\n"
        "Reply:"
    )

    return _call_llm(system_prompt).strip()


def build_chat_reply(trino_user, prompt, schema_summary, history=None):
    """
    CHAT-intent turn: answer in the chat only, never touching the dashboard.
    Tries to ground the answer in real data first (generate + run SQL,
    summarize the result) since most cross-questions are still data
    questions; falls back to a free-form conversational reply when the
    message isn't really answerable with a query (e.g. "thanks").
    """
    try:
        if wants_same_data(prompt) and history:
            sql = history[-1]["sql"]
        else:
            sql = generate_sql(prompt, schema_summary, history=history)

        result = TrinoQueryRunner(trino_user, schema=LAKEHOUSE_SCHEMA).run(sql)
        answer = generate_answer(prompt, result["columns"], result["rows"])
        return {"prompt": prompt, "answer": answer, "sql": sql}

    except (PromptToSqlError, QueryExecutionError):
        answer = free_chat_answer(prompt, history)
        return {"prompt": prompt, "answer": answer, "sql": None}


def _extract_sql(raw_text):
    """
    Pull a single SQL statement out of whatever the model returned -
    small models routinely wrap it in prose or markdown fences.
    """
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else raw_text

    match = re.search(r"select\b.*", candidate, re.DOTALL | re.IGNORECASE)
    if not match:
        raise PromptToSqlError("The model did not return a SQL query.")

    # Truncate to the first statement (defuses stacked queries) and drop the
    # trailing semicolon - Trino's parser rejects a statement that ends with
    # one (unlike the Postgres driver this used to run through).
    sql = match.group(0).strip()
    sql = sql.split(";")[0].strip()

    return sql


def _get_default_llm_model():
    model = LLMModel.objects.filter(is_default=True).first()

    if not model:
        raise PromptToSqlError(
            "No default LLM model is configured. Add one under AI/ML -> "
            "Models and mark it as default."
        )

    return model


def _call_llm(prompt_text):
    """
    Sends `prompt_text` as a single user message to whichever LLMModel is
    marked as the default (configured under AI/ML -> Models, not .env) and
    returns the raw text of its reply.
    """
    model = _get_default_llm_model()

    headers = {}
    if model.api_key:
        headers["Authorization"] = f"Bearer {model.api_key}"

    # `verify` needs a filesystem path, not the PEM text itself - write it
    # to a throwaway file for the duration of this one request.
    cert_file = None
    verify = True

    try:
        if model.ca_cert:
            cert_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".crt", delete=False
            )
            cert_file.write(model.ca_cert)
            cert_file.close()
            verify = cert_file.name

        response = requests.post(
            f"{model.api_base.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": model.model_name,
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0,
            },
            verify=verify,
            timeout=LLM_TIMEOUT,
        )
        response.raise_for_status()

    except requests.RequestException as ex:
        raise PromptToSqlError(f"Failed to reach the LLM: {str(ex)}")

    finally:
        if cert_file:
            os.unlink(cert_file.name)

    try:
        return response.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise PromptToSqlError("The LLM returned an unexpected response shape.")


def generate_sql(prompt, schema_summary, history=None):
    """
    Ask the organization's hosted LLM (an OpenAI-compatible vLLM endpoint)
    for a single read-only SQL statement answering `prompt` against
    `schema_summary`.

    `history` (a list of {"prompt": ..., "sql": ...} dicts, oldest first)
    lets a follow-up like "now show temperature vs pressure" inherit
    context (e.g. "for the machine") from what was asked before,
    chatbot-style.
    """
    history_block = ""
    if history:
        numbered = "\n".join(
            f"{i + 1}. {turn['prompt']}" for i, turn in enumerate(history)
        )
        history_block = (
            "Conversation so far (oldest first) - the new question below may "
            "omit context (like which machine, table, or time range) that "
            "was already established here. Carry that context forward "
            "explicitly; don't leave it implicit.\n"
            f"{numbered}\n\n"
        )

    system_prompt = (
        "You are a SQL generator for Trino, querying Iceberg tables in a "
        "data lakehouse. Table names are unqualified (the schema is already "
        "selected) - never prefix them with a catalog or schema name. Given "
        "a database schema and a question, respond with ONLY a single "
        "SELECT statement that answers the question - no explanation, no "
        "markdown fences, nothing but SQL.\n"
        "Never use INSERT, UPDATE, DELETE, DROP, ALTER, or any statement other "
        "than SELECT.\n"
        "When the question asks for a breakdown 'per X' or 'by X', you MUST "
        "GROUP BY that column and SELECT it alongside the aggregate - never "
        "filter on it with WHERE instead of grouping.\n"
        "Prefer exactly two output columns so the result can be charted: one "
        "label/dimension column (a name, category, or date/time column) and "
        "one numeric column (a raw value or an aggregate like SUM/AVG/COUNT).\n\n"
        "Example schema:\n"
        "orders(id integer, customer_name character varying, amount numeric, order_date timestamp)\n\n"
        "Example question: Show total amount per customer\n"
        "SQL: SELECT customer_name, SUM(amount) AS total_amount FROM orders GROUP BY customer_name;\n\n"
        "Example question: Show amount over time\n"
        "SQL: SELECT order_date, amount FROM orders ORDER BY order_date;\n\n"
        "Now answer this one the same way.\n\n"
        f"Schema:\n{schema_summary}\n\n"
        f"{history_block}"
        f"Question: {prompt}\n\n"
        "SQL:"
    )

    raw_text = _call_llm(system_prompt)
    sql = _extract_sql(raw_text)

    lowered = sql.lower()
    if not lowered.strip().startswith("select"):
        raise PromptToSqlError("Generated statement was not a SELECT query.")

    if any(keyword in lowered for keyword in BLOCKED_KEYWORDS):
        raise PromptToSqlError("Generated statement contained a disallowed keyword.")

    return sql


def generate_answer(prompt, columns, rows):
    """
    Ask the LLM for a short natural-language answer to `prompt`, grounded in
    the actual query result - this is the text shown in the chat bubble, not
    a canned "here's your chart" template.
    """
    max_preview_rows = 25
    header = ", ".join(columns)
    body = "\n".join(
        ", ".join("" if value is None else str(value) for value in row)
        for row in rows[:max_preview_rows]
    )
    truncated_note = "\n(more rows omitted)" if len(rows) > max_preview_rows else ""

    system_prompt = (
        "You are a data analyst. Answer the user's question in 1-3 short "
        "sentences, using only the query result data below. Be specific - "
        "cite actual numbers and names from the data. Do not mention SQL, "
        "charts, or tables. Do not repeat the question back.\n\n"
        f"Question: {prompt}\n\n"
        f"Result columns: {header}\n"
        f"Result rows:\n{body}{truncated_note}\n\n"
        "Answer:"
    )

    try:
        return _call_llm(system_prompt).strip()
    except PromptToSqlError:
        # The chart itself already succeeded - a flaky summary call
        # shouldn't fail the whole turn, so fall back to a plain sentence.
        return f"Here's your result — {len(rows)} row{'s' if len(rows) != 1 else ''}."


def infer_chart(columns, rows):
    """
    Deterministic chart-type inference from the actual result shape - the
    fallback used when the user didn't explicitly name a chart type.
    """
    if len(rows) == 1 and len(columns) == 1:
        return {"type": "number", "x_field": None, "y_field": columns[0]}

    numeric_cols = []
    other_cols = []

    for i, col in enumerate(columns):
        sample = next((row[i] for row in rows if row[i] is not None), None)
        if isinstance(sample, (int, float, Decimal)) and not isinstance(sample, bool):
            numeric_cols.append(col)
        else:
            other_cols.append(col)

    if len(other_cols) >= 1 and len(numeric_cols) >= 1:
        x_field = other_cols[0]
        y_field = numeric_cols[0]
        chart_type = "line" if _looks_temporal(x_field) else "bar"
        return {"type": chart_type, "x_field": x_field, "y_field": y_field}

    return {"type": "table", "x_field": None, "y_field": None}


def _looks_temporal(column_name):
    name = column_name.lower()
    return any(token in name for token in ("time", "date", "created", "updated", "at"))


def build_widget(trino_user, prompt, schema_summary, history=None):
    """
    One chat turn -> one chart: generate SQL (or reuse the previous turn's,
    if the user just wants the same data re-rendered), run it, and pick a
    chart type. Never raises - a failure comes back as an {"error": ...}
    entry so the caller can decide how to surface it (the UI hides it).
    """
    requested_type = detect_requested_chart_type(prompt)

    try:
        if wants_same_data(prompt) and history:
            sql = history[-1]["sql"]
        else:
            sql = generate_sql(prompt, schema_summary, history=history)

        result = TrinoQueryRunner(trino_user, schema=LAKEHOUSE_SCHEMA).run(sql)
        chart = infer_chart(result["columns"], result["rows"])

        if requested_type:
            chart["type"] = requested_type

        answer = generate_answer(prompt, result["columns"], result["rows"])

        return {
            "prompt": prompt,
            "sql": sql,
            "columns": result["columns"],
            "rows": result["rows"],
            "row_count": result["row_count"],
            "truncated": result["truncated"],
            "duration_ms": result["duration_ms"],
            "chart": chart,
            "answer": answer,
        }

    except (PromptToSqlError, QueryExecutionError) as ex:
        return {
            "prompt": prompt,
            "error": str(ex),
        }


NUMBER_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a couple of": 2, "a few": 3, "several": 4,
}
MAX_MULTI_CHARTS = 8

_MULTI_CHART_DIGIT_PATTERN = re.compile(r"\b(\d+)\s+(?:different\s+|new\s+|more\s+)*charts?\b")


def wants_multi_chart(prompt):
    """
    Returns how many charts the message is asking for at once (e.g.
    "create 8 different charts with random data", "give me 3 charts"), or
    None if it's a normal single-chart request.
    """
    lowered = prompt.lower()

    digit_match = _MULTI_CHART_DIGIT_PATTERN.search(lowered)
    if digit_match:
        return min(int(digit_match.group(1)), MAX_MULTI_CHARTS)

    for word, count in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\s+(?:different\s+|new\s+|more\s+)*charts?\b", lowered):
            return min(count, MAX_MULTI_CHARTS)

    if "multiple charts" in lowered or "several charts" in lowered:
        return 4

    return None


def generate_chart_questions(prompt, schema_summary, count, history=None):
    """
    Turns a bulk request ("create 8 different charts with random data")
    into `count` distinct, answerable questions grounded in the real
    schema - the model is explicitly told not to invent fake/random data,
    since there's nothing in a lakehouse table to make a chart "random".
    """
    history_block = ""
    if history:
        numbered = "\n".join(
            f"{i + 1}. {turn['prompt']}" for i, turn in enumerate(history)
        )
        history_block = f"Conversation so far (oldest first):\n{numbered}\n\n"

    system_prompt = (
        f"The user wants {count} different charts at once. Propose exactly "
        f"{count} distinct, meaningful questions that can each be answered "
        "with a SELECT query against the schema below - different tables, "
        "columns, aggregations, or breakdowns so the charts aren't "
        "repetitive. Never invent random or fake data - every question "
        "must be answerable from the real schema.\n"
        f"Respond with ONLY a JSON array of exactly {count} short question "
        "strings (no prose, no markdown fences), e.g. "
        '["Show total X per Y", "Show Z over time", ...].\n\n'
        f"Schema:\n{schema_summary}\n\n"
        f"{history_block}"
        f"User's message: {prompt}\n\n"
        "JSON array:"
    )

    try:
        raw_text = _call_llm(system_prompt)
    except PromptToSqlError:
        return []

    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else raw_text

    match = re.search(r"\[.*\]", candidate, re.DOTALL)
    if not match:
        return []

    try:
        questions = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    if not isinstance(questions, list):
        return []

    return [str(q).strip() for q in questions if str(q).strip()][:count]


def build_multiple_widgets(trino_user, prompt, schema_summary, count, history=None):
    """
    Bulk version of build_widget() - turns one "create N charts" message
    into up to `count` real widgets, each grounded in actual query results.
    Questions that fail to produce a valid chart are silently skipped
    (rather than failing the whole batch) since one bad sub-question
    shouldn't block the other N-1 good ones.
    """
    questions = generate_chart_questions(prompt, schema_summary, count, history=history)

    widgets = []
    for question in questions:
        widget = build_widget(trino_user, question, schema_summary, history=history)
        if "error" not in widget:
            widgets.append(widget)

    return widgets

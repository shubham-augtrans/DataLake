import re
from decimal import Decimal

import requests
from django.conf import settings

from apps.query.services import LAKEHOUSE_SCHEMA, QueryExecutionError, TrinoQueryRunner

OLLAMA_TIMEOUT = 60
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


def generate_sql(prompt, schema_summary, history=None):
    """
    Ask the local Ollama model for a single read-only SQL statement
    answering `prompt` against `schema_summary`.

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

    try:
        response = requests.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": system_prompt,
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()

    except requests.RequestException as ex:
        raise PromptToSqlError(f"Failed to reach Ollama: {str(ex)}")

    raw_text = response.json().get("response", "")
    sql = _extract_sql(raw_text)

    lowered = sql.lower()
    if not lowered.strip().startswith("select"):
        raise PromptToSqlError("Generated statement was not a SELECT query.")

    if any(keyword in lowered for keyword in BLOCKED_KEYWORDS):
        raise PromptToSqlError("Generated statement contained a disallowed keyword.")

    return sql


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

        return {
            "prompt": prompt,
            "sql": sql,
            "columns": result["columns"],
            "rows": result["rows"],
            "row_count": result["row_count"],
            "truncated": result["truncated"],
            "duration_ms": result["duration_ms"],
            "chart": chart,
        }

    except (PromptToSqlError, QueryExecutionError) as ex:
        return {
            "prompt": prompt,
            "error": str(ex),
        }

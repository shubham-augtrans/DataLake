import re
from decimal import Decimal

import requests
from django.conf import settings

from apps.query.services import PostgresQueryRunner, QueryExecutionError

OLLAMA_TIMEOUT = 60
BLOCKED_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter",
    "truncate", "grant", "revoke", "create", "replace",
)


class PromptToSqlError(Exception):
    pass


def fetch_schema_summary(datasource, max_tables=15, max_columns_per_table=20):
    """
    Compact "table(col type, col type, ...)" schema listing for a Postgres
    DataSource, used as grounding context for the LLM prompt.
    """
    runner = PostgresQueryRunner(datasource)

    result = runner.run("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """)

    tables = {}
    for table_name, column_name, data_type in result["rows"]:
        columns = tables.setdefault(table_name, [])
        if len(columns) < max_columns_per_table:
            columns.append(f"{column_name} {data_type}")

    lines = [
        f"{table}({', '.join(columns)})"
        for table, columns in list(tables.items())[:max_tables]
    ]

    return "\n".join(lines)


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

    sql = match.group(0).strip()
    sql = sql.split(";")[0].strip() + ";"

    return sql


def generate_sql(datasource, prompt, schema_summary):
    """
    Ask the local Ollama model for a single read-only SQL statement
    answering `prompt` against `schema_summary`.
    """
    system_prompt = (
        "You are a SQL generator for PostgreSQL. Given a database schema and a "
        "question, respond with ONLY a single SELECT statement that answers the "
        "question - no explanation, no markdown fences, nothing but SQL.\n"
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
    Deterministic chart-type inference from the actual result shape -
    not trusted to the (very small) LLM.
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

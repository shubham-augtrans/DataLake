import time

import psycopg2
import psycopg2.extras
import trino
import trino.exceptions
from django.conf import settings

MAX_ROWS = 500
STATEMENT_TIMEOUT_MS = 30_000


class QueryExecutionError(Exception):
    pass


class QueryAuthorizationError(QueryExecutionError):
    """
    Raised when Trino/Ranger denies the requesting user access - kept distinct
    from a generic execution error so callers can return 403 instead of 400.
    """
    pass


class PostgresQueryRunner:
    """
    Executes a single SQL statement against a PostgreSQL-type DataSource.
    """

    def __init__(self, datasource):
        if datasource.source_type != "postgres":
            raise QueryExecutionError(
                f"SQL execution is only supported for PostgreSQL sources, "
                f"got '{datasource.source_type}'."
            )

        self.datasource = datasource
        self.config = datasource.configuration or {}

    def _connect(self):
        try:
            return psycopg2.connect(
                host=self.config["host"],
                port=self.config.get("port", 5432),
                dbname=self.config["database"],
                user=self.config["username"],
                password=self.config.get("password"),
                connect_timeout=10,
            )
        except KeyError as ex:
            raise QueryExecutionError(
                f"Data source is missing required connection field: {ex}"
            )
        except psycopg2.OperationalError as ex:
            raise QueryExecutionError(f"Failed to connect: {str(ex)}")

    def run(self, sql_text):
        sql_text = (sql_text or "").strip()

        if not sql_text:
            raise QueryExecutionError("No SQL statement provided.")

        started = time.monotonic()

        conn = self._connect()

        try:
            conn.autocommit = True

            with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:

                cursor.execute(
                    f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}"
                )

                cursor.execute(sql_text)

                if cursor.description is not None:
                    rows = cursor.fetchmany(MAX_ROWS)
                    columns = [col.name for col in cursor.description]

                    result_rows = [
                        [row[col] for col in columns]
                        for row in rows
                    ]

                    duration_ms = int(
                        (time.monotonic() - started) * 1000
                    )

                    return {
                        "columns": columns,
                        "rows": result_rows,
                        "row_count": len(result_rows),
                        "truncated": len(result_rows) == MAX_ROWS,
                        "duration_ms": duration_ms,
                    }

                duration_ms = int(
                    (time.monotonic() - started) * 1000
                )

                return {
                    "columns": [],
                    "rows": [],
                    "row_count": cursor.rowcount,
                    "truncated": False,
                    "duration_ms": duration_ms,
                }

        except psycopg2.Error as ex:
            raise QueryExecutionError(str(ex).strip())

        finally:
            conn.close()


class TrinoQueryRunner:
    """
    Executes a single SQL statement against Trino as a specific,
    authenticated user - so that Apache Ranger's per-user policies
    (enforced by Trino's Ranger access-control plugin) are checked
    against the real caller, not a shared service account.
    """

    def __init__(self, trino_user):
        if not trino_user:
            raise QueryExecutionError("A Trino user identity is required.")

        self.trino_user = trino_user

    def _connect(self):
        return trino.dbapi.connect(
            host=settings.TRINO_HOST,
            port=settings.TRINO_PORT,
            user=self.trino_user,
            catalog=settings.TRINO_CATALOG,
            http_scheme="http",
        )

    def run(self, sql_text):
        sql_text = (sql_text or "").strip()

        if not sql_text:
            raise QueryExecutionError("No SQL statement provided.")

        started = time.monotonic()

        conn = self._connect()

        try:
            cursor = conn.cursor()

            try:
                cursor.execute(sql_text)
                rows = cursor.fetchmany(MAX_ROWS)

            except trino.exceptions.TrinoUserError as ex:
                message = str(ex)

                if "Access Denied" in message:
                    raise QueryAuthorizationError(
                        f"Access denied for user '{self.trino_user}': {message}"
                    )

                raise QueryExecutionError(message)

            columns = [col[0] for col in cursor.description] if cursor.description else []
            duration_ms = int((time.monotonic() - started) * 1000)

            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "row_count": len(rows),
                "truncated": len(rows) == MAX_ROWS,
                "duration_ms": duration_ms,
            }

        finally:
            conn.close()

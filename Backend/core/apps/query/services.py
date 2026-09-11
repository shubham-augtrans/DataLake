import time

import trino
import trino.exceptions
from django.conf import settings

MAX_ROWS = 500

# Schema every ingestion pipeline writes into (see spark_runner.target_table) -
# the SQL Editor defaults to it so plain, unqualified table names resolve
# against the lakehouse copy in MinIO instead of requiring iceberg.ingested.<table>.
LAKEHOUSE_SCHEMA = "ingested"


class QueryExecutionError(Exception):
    pass


class QueryAuthorizationError(QueryExecutionError):
    """
    Raised when Trino/Ranger denies the requesting user access - kept distinct
    from a generic execution error so callers can return 403 instead of 400.
    """
    pass


class TrinoQueryRunner:
    """
    Executes a single SQL statement against Trino as a specific,
    authenticated user - so that Apache Ranger's per-user policies
    (enforced by Trino's Ranger access-control plugin) are checked
    against the real caller, not a shared service account.
    """

    def __init__(self, trino_user, schema=None):
        if not trino_user:
            raise QueryExecutionError("A Trino user identity is required.")

        self.trino_user = trino_user
        self.schema = schema

    def _connect(self):
        kwargs = dict(
            host=settings.TRINO_HOST,
            port=settings.TRINO_PORT,
            user=self.trino_user,
            catalog=settings.TRINO_CATALOG,
            http_scheme="http",
        )

        if self.schema:
            kwargs["schema"] = self.schema

        return trino.dbapi.connect(**kwargs)

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

            except trino.exceptions.TrinoQueryError as ex:
                # Covers both user errors (bad SQL) and external/internal
                # errors (e.g. the Iceberg REST catalog being unreachable) -
                # either way the caller gets a clean message, not a raw 500.
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

    def list_catalogs(self):
        """
        Catalogs visible to this user (per Ranger's catalog-level rules).
        """
        result = self.run("SHOW CATALOGS")
        return [row[0] for row in result["rows"]]

    def list_schemas(self, catalog):
        """
        Schemas within a catalog. Goes through the same Ranger-governed
        connection as any other query, so a user only sees what they're
        authorized to see.
        """
        result = self.run(f'SHOW SCHEMAS FROM "{catalog}"')
        return [row[0] for row in result["rows"]]

    def list_tables(self, catalog, schema):
        result = self.run(f'SHOW TABLES FROM "{catalog}"."{schema}"')
        return [row[0] for row in result["rows"]]

    def list_columns(self, catalog, schema, table):
        result = self.run(f'DESCRIBE "{catalog}"."{schema}"."{table}"')
        return [
            {"name": row[0], "type": row[1]}
            for row in result["rows"]
        ]

import psycopg2
from psycopg2.extras import execute_values

from connectors.destination.base import BaseDestinationConnector
from sqlalchemy import create_engine

class PostgresConnector(BaseDestinationConnector):
    """
    PostgreSQL Destination Connector
    """

    def __init__(self, destination):

        self.destination = destination
        config = destination.configuration

        self.connection = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["username"],
            password=config["password"],
        )

        self.connection.autocommit = True

    def check_connection(self):
        """
        Test PostgreSQL connection.
        """
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            return cursor.fetchone()[0] == 1

    def execute(self, query, params=None):
        """
        Execute any SQL query.
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)

    def fetch_all(self, query, params=None):
        """
        Execute a SELECT query.
        """
        with self.connection.cursor() as cursor:

            cursor.execute(query, params)

            columns = [
                desc[0]
                for desc in cursor.description
            ]

            rows = cursor.fetchall()

            return [
                dict(zip(columns, row))
                for row in rows
            ]

    def insert_rows(self, table_name, rows):
        """
        Insert multiple rows into a PostgreSQL table.

        rows = [
            {
                "id":1,
                "name":"Alice"
            },
            {
                "id":2,
                "name":"Bob"
            }
        ]
        """

        if not rows:
            return

        columns = list(rows[0].keys())

        values = [
            tuple(row[col] for col in columns)
            for row in rows
        ]

        sql = f"""
            INSERT INTO {table_name}
            ({','.join(columns)})
            VALUES %s
        """

        with self.connection.cursor() as cursor:
            execute_values(
                cursor,
                sql,
                values
            )

    def write_dataframe(self, dataframe, table_name):

        config = self.destination.configuration

        engine = create_engine(
            f"postgresql://"
            f"{config['username']}:{config['password']}"
            f"@{config['host']}:{config['port']}"
            f"/{config['database']}"
        )

        dataframe.to_sql(
            table_name,
            engine,
            if_exists="replace",
            index=False,
        )
    def close(self):
        if self.connection:
            self.connection.close()
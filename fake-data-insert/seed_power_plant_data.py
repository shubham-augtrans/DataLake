"""
Seeds sample power plant sensor readings into PostgreSQL.

Connects to the "datalake" Postgres instance, creates a
`power_plant_readings` table if it doesn't exist, and inserts
at least 10 sample records (machine name, pressure, temperature,
reading time).

Usage:
    python seed_power_plant_data.py
"""

import random
from datetime import datetime, timedelta

import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "datalake",
    "user": "shubham",
    "password": "Shubham@123456",
}

MACHINES = [
    "Siemens Turbine-1",
    "Siemens Turbine-2",
    "Siemens Compressor-1",
    "Siemens Generator-1",
]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS power_plant_readings (
    id SERIAL PRIMARY KEY,
    machine_name VARCHAR(100) NOT NULL,
    pressure NUMERIC(6, 2) NOT NULL,
    temperature NUMERIC(6, 2) NOT NULL,
    reading_time TIMESTAMP NOT NULL
);
"""

INSERT_SQL = """
INSERT INTO power_plant_readings (machine_name, pressure, temperature, reading_time)
VALUES (%s, %s, %s, %s);
"""


def generate_records(count=15):
    """
    Build `count` sample readings with slightly randomized
    pressure/temperature values, spaced 10 minutes apart.
    """
    records = []
    base_time = datetime.now()

    for i in range(count):
        records.append((
            random.choice(MACHINES),
            round(random.uniform(8.0, 15.0), 2),      # pressure in bar
            round(random.uniform(60.0, 120.0), 2),    # temperature in °C
            base_time - timedelta(minutes=10 * i),
        ))

    return records


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True

    try:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)

            records = generate_records(15)
            cursor.executemany(INSERT_SQL, records)

            print(f"Inserted {len(records)} records into power_plant_readings.")

            cursor.execute(
                "SELECT id, machine_name, pressure, temperature, reading_time "
                "FROM power_plant_readings ORDER BY id DESC LIMIT %s;",
                (len(records),),
            )

            for row in cursor.fetchall():
                print(row)

    finally:
        conn.close()


if __name__ == "__main__":
    main()

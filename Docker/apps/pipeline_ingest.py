"""
Generic Ingestion pipeline: Spark -> Iceberg REST Catalog -> MinIO.

Parameterized sibling of iceberg_demo.py, which is the proven reference for
this project's Spark/Iceberg config (catalog alias, warehouse, MinIO S3
settings, and the iceberg-spark-runtime/iceberg-aws-bundle version pin for
Java 11 compatibility with apache/spark:3.5.6 - see that file's docstring).

Reads the raw JSON batch NiFi landed in the MinIO staging bucket, does a
minimal generic cleaning pass (drop rows missing required fields, dedupe),
and writes the result into an Iceberg table - that write is what actually
converts the data to Parquet and lands it in MinIO, while registering the
new snapshot in the Iceberg REST catalog.

Usage:
    spark-submit ... pipeline_ingest.py <staging_path> <table>

    staging_path: s3a://staging/<pipeline_id>/data.json
    table:        lakehouse.ingested.<slug(source_object)>
"""

import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def build_spark_session():
    return SparkSession.builder.appName("pipeline-ingest").getOrCreate()


def preprocess(raw_df):
    """
    Generic cleaning pass - no domain-specific rules, since this must work
    for any ingested table: drop rows missing any field, dedupe exact
    duplicates.
    """
    non_null_condition = None

    for column in raw_df.columns:
        condition = F.col(column).isNotNull()
        non_null_condition = condition if non_null_condition is None else (non_null_condition & condition)

    df = raw_df if non_null_condition is None else raw_df.filter(non_null_condition)

    return df.dropDuplicates()


def main():
    if len(sys.argv) != 3:
        print("Usage: pipeline_ingest.py <staging_path> <table>")
        sys.exit(1)

    staging_path = sys.argv[1]
    table = sys.argv[2]

    namespace = ".".join(table.split(".")[:-1])

    spark = build_spark_session()

    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {namespace}")

    raw_df = spark.read.json(staging_path)
    clean_df = preprocess(raw_df)

    print(f"Raw rows: {raw_df.count()} -> Clean rows after preprocessing: {clean_df.count()}")

    if spark.catalog.tableExists(table):
        clean_df.writeTo(table).append()
    else:
        clean_df.writeTo(table).using("iceberg").createOrReplace()

    print(f"Wrote {clean_df.count()} rows to {table}")

    spark.stop()


if __name__ == "__main__":
    main()

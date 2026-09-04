"""
End-to-end demo: Spark -> Iceberg REST Catalog -> MinIO.

Simulates the "Spark preprocessing" stage of the pipeline
(Data Source -> NiFi -> Spark -> Iceberg REST Catalog -> MinIO):
reads a batch of raw power-plant sensor readings, cleanses/validates/
deduplicates/type-converts them in Spark, then writes the result into
an Iceberg table via the REST catalog, whose data/metadata files land
in MinIO.

Run via spark-submit against the existing spark-master cluster, e.g.:

    docker run --rm --network docker_iceberg_net \
      -v "$(pwd)/apps:/opt/spark-apps" -v "$(pwd)/ivy-cache:/tmp/ivy" \
      -e AWS_ACCESS_KEY_ID=shubham -e AWS_SECRET_ACCESS_KEY=Shubham@123456 -e AWS_REGION=us-east-1 \
      apache/spark:3.5.6 /opt/spark/bin/spark-submit \
      --master spark://spark-master:7077 --deploy-mode client \
      --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,org.apache.iceberg:iceberg-aws-bundle:1.6.1 \
      --conf spark.jars.ivy=/tmp/ivy \
      --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
      --conf spark.sql.catalog.lakehouse=org.apache.iceberg.spark.SparkCatalog \
      --conf spark.sql.catalog.lakehouse.type=rest \
      --conf spark.sql.catalog.lakehouse.uri=http://iceberg-rest:8181 \
      --conf spark.sql.catalog.lakehouse.io-impl=org.apache.iceberg.aws.s3.S3FileIO \
      --conf spark.sql.catalog.lakehouse.warehouse=s3://warehouse/ \
      --conf spark.sql.catalog.lakehouse.s3.endpoint=http://minio:9000 \
      --conf spark.sql.catalog.lakehouse.s3.path-style-access=true \
      /opt/spark-apps/iceberg_demo.py

NOTE on versions: iceberg-spark-runtime/iceberg-aws-bundle 1.11.0 (the
current latest Iceberg release) are compiled for Java 17 and will fail
with UnsupportedClassVersionError on this project's apache/spark:3.5.6
image, which ships Java 11. 1.6.1 is the newest Iceberg release still
built for a Java 11 target and is what this project pins to; upgrading
would require switching to a Java 17 Spark base image.
    --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
    --conf spark.sql.catalog.lakehouse=org.apache.iceberg.spark.SparkCatalog
    --conf spark.sql.catalog.lakehouse.type=rest
    --conf spark.sql.catalog.lakehouse.uri=http://iceberg-rest:8181
    --conf spark.sql.catalog.lakehouse.io-impl=org.apache.iceberg.aws.s3.S3FileIO
    --conf spark.sql.catalog.lakehouse.warehouse=s3://warehouse/
    --conf spark.sql.catalog.lakehouse.s3.endpoint=http://minio:9000
    --conf spark.sql.catalog.lakehouse.s3.path-style-access=true

AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION are picked up from
the container's environment (already set on spark-master/spark-worker in
docker-compose.yml) - no credentials are hard-coded here.
"""

from pyspark.sql import Row, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StringType,
    StructField,
    StructType,
    TimestampType,
)

CATALOG = "lakehouse"
NAMESPACE = "plant_ops"
TABLE = f"{CATALOG}.{NAMESPACE}.machine_readings"

RAW_SCHEMA = StructType([
    StructField("machine_name", StringType(), True),
    StructField("pressure", StringType(), True),      # arrives as text from the source
    StructField("temperature", StringType(), True),   # arrives as text from the source
    StructField("reading_time", StringType(), True),
])


def build_spark_session():
    return SparkSession.builder.appName("iceberg-demo").getOrCreate()


def load_raw_batch(spark):
    """
    Stand-in for the batch NiFi would hand off to Spark: raw, untyped,
    with a duplicate and a bad row mixed in on purpose so the
    preprocessing step below has something real to do.
    """
    rows = [
        Row("Siemens Turbine-1", "9.86", "68.95", "2026-09-04 10:00:00"),
        Row("Siemens Turbine-1", "9.86", "68.95", "2026-09-04 10:00:00"),  # duplicate
        Row("Siemens Turbine-2", "12.03", "110.14", "2026-09-04 10:10:00"),
        Row("Siemens Compressor-1", "8.64", "94.90", "2026-09-04 10:20:00"),
        Row("Siemens Generator-1", "14.60", "82.16", "2026-09-04 10:30:00"),
        Row(None, "11.27", "74.08", "2026-09-04 10:40:00"),  # invalid: no machine name
        Row("Siemens Generator-1", "not-a-number", "89.88", "2026-09-04 10:50:00"),  # invalid pressure
    ]
    return spark.createDataFrame(rows, schema=RAW_SCHEMA)


def preprocess(raw_df):
    """
    The actual Spark processing layer: type conversion, validation,
    filtering, and deduplication before the data is fit to land in
    Iceberg.
    """
    return (
        raw_df
        .withColumn("pressure", F.col("pressure").cast("double"))
        .withColumn("temperature", F.col("temperature").cast("double"))
        .withColumn("reading_time", F.to_timestamp("reading_time"))
        # data quality: drop rows missing required fields or with values
        # that failed to cast (cast() returns null on failure)
        .filter(
            F.col("machine_name").isNotNull()
            & F.col("pressure").isNotNull()
            & F.col("temperature").isNotNull()
            & F.col("reading_time").isNotNull()
        )
        # deduplicate identical readings
        .dropDuplicates(["machine_name", "reading_time"])
        # enrichment: normalize machine names, flag pressure outliers
        .withColumn("machine_name", F.trim(F.col("machine_name")))
        .withColumn(
            "is_pressure_anomaly",
            F.when((F.col("pressure") < 8.0) | (F.col("pressure") > 15.0), True).otherwise(False),
        )
    )


def main():
    spark = build_spark_session()

    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{NAMESPACE}")

    raw_df = load_raw_batch(spark)
    clean_df = preprocess(raw_df)

    print(f"Raw rows: {raw_df.count()} -> Clean rows after preprocessing: {clean_df.count()}")

    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            machine_name STRING,
            pressure DOUBLE,
            temperature DOUBLE,
            reading_time TIMESTAMP,
            is_pressure_anomaly BOOLEAN
        )
        USING iceberg
        PARTITIONED BY (days(reading_time))
    """)

    clean_df.writeTo(TABLE).append()

    print(f"Wrote {clean_df.count()} rows to {TABLE}")

    print("Reading back from Iceberg:")
    spark.table(TABLE).orderBy("reading_time").show(truncate=False)

    spark.sql(f"SELECT * FROM {TABLE}.snapshots").show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()

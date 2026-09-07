import re
import subprocess

from django.conf import settings

SPARK_SUBMIT_TIMEOUT = 300


class SparkIngestError(Exception):
    pass


def _slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return slug.strip("_") or "table"


def target_table(pipeline):
    return f"lakehouse.ingested.{_slugify(pipeline.source_object)}"


def run_spark_ingest(pipeline, staging_path):
    """
    Runs pipeline_ingest.py via a throwaway `docker run` against the existing
    spark-master cluster - the same invocation shape documented (and proven
    working) in Docker/apps/iceberg_demo.py's docstring. Not `docker exec
    spark-master`: that container has no volume mount for the apps directory,
    so the script has to be supplied from a fresh container instead.
    """

    table = target_table(pipeline)

    command = [
        "docker", "run", "--rm",
        "--network", "docker_iceberg_net",
        "-v", f"{settings.SPARK_APPS_HOST_PATH}:/opt/spark-apps",
        "-v", f"{settings.SPARK_IVY_CACHE_HOST_PATH}:/tmp/ivy",
        "-e", "AWS_ACCESS_KEY_ID=shubham",
        "-e", "AWS_SECRET_ACCESS_KEY=Shubham@123456",
        "-e", "AWS_REGION=us-east-1",
        "apache/spark:3.5.6",
        "/opt/spark/bin/spark-submit",
        "--master", "spark://spark-master:7077",
        "--deploy-mode", "client",
        "--packages", "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,org.apache.iceberg:iceberg-aws-bundle:1.6.1,org.apache.hadoop:hadoop-aws:3.3.4",
        "--conf", "spark.jars.ivy=/tmp/ivy",
        "--conf", "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        "--conf", "spark.sql.catalog.lakehouse=org.apache.iceberg.spark.SparkCatalog",
        "--conf", "spark.sql.catalog.lakehouse.type=rest",
        "--conf", f"spark.sql.catalog.lakehouse.uri={settings.SPARK_ICEBERG_REST_URL}",
        "--conf", "spark.sql.catalog.lakehouse.io-impl=org.apache.iceberg.aws.s3.S3FileIO",
        "--conf", "spark.sql.catalog.lakehouse.warehouse=s3://warehouse/",
        "--conf", f"spark.sql.catalog.lakehouse.s3.endpoint={settings.SPARK_MINIO_ENDPOINT}",
        "--conf", "spark.sql.catalog.lakehouse.s3.path-style-access=true",
        # Generic s3a:// reads (for the raw staging file) go through
        # hadoop-aws, a separate config namespace from Iceberg's own S3FileIO
        # (spark.sql.catalog.lakehouse.s3.*) used for the warehouse above.
        "--conf", "spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem",
        "--conf", f"spark.hadoop.fs.s3a.endpoint={settings.SPARK_MINIO_ENDPOINT}",
        "--conf", "spark.hadoop.fs.s3a.access.key=shubham",
        "--conf", "spark.hadoop.fs.s3a.secret.key=Shubham@123456",
        "--conf", "spark.hadoop.fs.s3a.path.style.access=true",
        "/opt/spark-apps/pipeline_ingest.py",
        staging_path,
        table,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=SPARK_SUBMIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as ex:
        raise SparkIngestError(f"Spark job timed out after {SPARK_SUBMIT_TIMEOUT}s: {ex}")

    if result.returncode != 0:
        raise SparkIngestError(
            f"spark-submit exited {result.returncode}\n"
            f"stdout:\n{result.stdout[-2000:]}\n"
            f"stderr:\n{result.stderr[-2000:]}"
        )

    return {"table": table, "stdout": result.stdout}

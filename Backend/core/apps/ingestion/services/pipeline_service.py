import time

from apps.ingestion.services.job_builder import (
    PostgresToMinioJobBuilder,
    MongoToMinioJobBuilder,
    KafkaToMinioJobBuilder
)
from apps.ingestion.services.nifi_client import NiFiClient
from apps.ingestion.services.spark_runner import SparkIngestError, run_spark_ingest

DRAIN_POLL_INTERVAL = 2
DRAIN_TIMEOUT = 60


class PipelineService:

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):

        source_type = (
            self.pipeline.source.source_type
        )

        destination_type = (
            self.pipeline.destination.destination_type
        )

        if (
            source_type == "postgres"
            and destination_type == "minio"
        ):
            return self._postgres_to_minio()

        elif (
            source_type == "mongo"
            and destination_type == "minio"
        ):
            return self._mongo_to_minio()

        elif (
            source_type == "kafka"
            and destination_type == "minio"
        ):
            return self._kafka_to_minio()

        raise Exception(
            f"Unsupported pipeline: "
            f"{source_type} -> {destination_type}"
        )

    def _postgres_to_minio(self):

        builder = PostgresToMinioJobBuilder(
            self.pipeline
        )

        result = builder.build()

        self.pipeline.nifi_process_group_id = (
            result["process_group_id"]
        )

        self.pipeline.nifi_source_processor_id = (
            result["source_processor_id"]
        )

        self.pipeline.nifi_destination_processor_id = (
            result["destination_processor_id"]
        )

        self.pipeline.save(
            update_fields=[
                "nifi_process_group_id",
                "nifi_source_processor_id",
                "nifi_destination_processor_id",
            ]
        )

        try:
            builder.start(result)
            self._wait_for_drain(result["process_group_id"])
            builder.stop(result)

            spark_result = run_spark_ingest(self.pipeline, result["staging_path"])

            self.pipeline.nifi_status = "success"
            self.pipeline.nifi_last_error = None
            result["table"] = spark_result["table"]

        except SparkIngestError as ex:
            builder.stop(result)
            self.pipeline.nifi_status = "error"
            self.pipeline.nifi_last_error = str(ex)
            raise

        finally:
            self.pipeline.save(
                update_fields=["nifi_status", "nifi_last_error"]
            )

        return result

    def _wait_for_drain(self, process_group_id):
        """
        Waits for the batch NiFi just started to finish flowing through the
        pipeline (queued flowfiles back to 0) before stopping the processors
        and handing off to Spark - bounded so a stuck/misconfigured flow
        can't hang the request forever.
        """

        nifi = NiFiClient()
        deadline = time.monotonic() + DRAIN_TIMEOUT

        # QueryDatabaseTableRecord needs a moment to start producing before
        # there's anything to drain - avoid a false "drained" read at t=0.
        time.sleep(DRAIN_POLL_INTERVAL)

        while time.monotonic() < deadline:
            status = nifi.get_process_group_status(process_group_id)
            queued = status["processGroupStatus"]["aggregateSnapshot"]["flowFilesQueued"]

            if queued == 0:
                return

            time.sleep(DRAIN_POLL_INTERVAL)

    def _mongo_to_minio(self):

        builder = MongoToMinioJobBuilder(
            self.pipeline
        )

        result = builder.build()

        self.pipeline.nifi_process_group_id = (
            result["process_group_id"]
        )

        self.pipeline.nifi_source_processor_id = (
            result["source_processor_id"]
        )

        self.pipeline.nifi_destination_processor_id = (
            result["destination_processor_id"]
        )

        self.pipeline.save(
            update_fields=[
                "nifi_process_group_id",
                "nifi_source_processor_id",
                "nifi_destination_processor_id",
            ]
        )

        return result

    def _kafka_to_minio(self):

        builder = KafkaToMinioJobBuilder(
            self.pipeline
        )

        result = builder.build()

        self.pipeline.nifi_process_group_id = (
            result["process_group_id"]
        )

        self.pipeline.nifi_source_processor_id = (
            result["source_processor_id"]
        )

        self.pipeline.nifi_destination_processor_id = (
            result["destination_processor_id"]
        )

        self.pipeline.save(
            update_fields=[
                "nifi_process_group_id",
                "nifi_source_processor_id",
                "nifi_destination_processor_id",
            ]
        )

        return result

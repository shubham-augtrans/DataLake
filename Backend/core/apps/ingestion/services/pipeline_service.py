from apps.ingestion.services.job_builder import (
    PostgresToMinioJobBuilder,
    MongoToMinioJobBuilder
)


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

        return result

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
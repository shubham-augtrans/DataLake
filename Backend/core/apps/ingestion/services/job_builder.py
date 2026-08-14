from django.conf import settings

from apps.ingestion.services.nifi_client import NiFiClient


class PostgresToMinioJobBuilder:

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.nifi = NiFiClient()

    def build(self):

        group = self._create_process_group()

        group_id = group["id"]

        postgres = self._create_postgres_processor(
            group_id
        )

        convert = self._create_convert_record(
            group_id
        )

        minio = self._create_minio_processor(
            group_id
        )

        self.nifi.create_connection(
            group_id,
            postgres["id"],
            convert["id"],
        )

        self.nifi.create_connection(
            group_id,
            convert["id"],
            minio["id"],
        )

        return {
            "process_group_id": group_id,
            "source_processor_id": postgres["id"],
            "destination_processor_id": minio["id"],
        }

    def _create_process_group(self):

        root_group_id = (
            self.nifi.get_root_process_group_id()
        )

        return self.nifi.create_process_group(
            parent_process_group_id=root_group_id,
            name=self.pipeline.name,
        )

    def _create_postgres_processor(
        self,
        group_id,
    ):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=(
                "org.apache.nifi.processors.db."
                "QueryDatabaseTableRecord"
            ),
            name="PostgreSQL Source",
            x=0,
            y=0,
        )

    def _create_convert_record(
        self,
        group_id,
    ):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=(
                "org.apache.nifi.processors.standard."
                "ConvertRecord"
            ),
            name="Convert to Parquet",
            x=400,
            y=0,
        )

    def _create_minio_processor(
        self,
        group_id,
    ):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=(
                "org.apache.nifi.processors.aws.s3."
                "PutS3Object"
            ),
            name="MinIO Destination",
            x=800,
            y=0,
        )


class MongoToMinioJobBuilder:

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.nifi = NiFiClient()

    def build(self):

        group = self._create_process_group()

        group_id = group["id"]

        mongo = self._create_mongo_processor(
            group_id
        )

        convert = self._create_convert_record(
            group_id
        )

        minio = self._create_minio_processor(
            group_id
        )

        self.nifi.create_connection(
            group_id,
            mongo["id"],
            convert["id"],
        )

        self.nifi.create_connection(
            group_id,
            convert["id"],
            minio["id"],
        )

        return {
            "process_group_id": group_id,
            "source_processor_id": mongo["id"],
            "destination_processor_id": minio["id"],
        }

    def _create_process_group(self):

        root_group_id = (
            self.nifi.get_root_process_group_id()
        )

        return self.nifi.create_process_group(
            parent_process_group_id=root_group_id,
            name=self.pipeline.name,
        )

    def _create_mongo_processor(
        self,
        group_id,
    ):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=(
                "org.apache.nifi.processors.mongodb."
                "GetMongoRecord"
            ),
            name="MongoDB Source",
            x=0,
            y=0,
        )

    def _create_convert_record(
        self,
        group_id,
    ):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=(
                "org.apache.nifi.processors.standard."
                "ConvertRecord"
            ),
            name="Convert to Parquet",
            x=400,
            y=0,
        )

    def _create_minio_processor(
        self,
        group_id,
    ):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=(
                "org.apache.nifi.processors.aws.s3."
                "PutS3Object"
            ),
            name="MinIO Destination",
            x=800,
            y=0,
        )
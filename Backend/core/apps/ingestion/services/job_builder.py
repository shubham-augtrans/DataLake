from django.conf import settings

from apps.ingestion.services.nifi_client import NiFiClient


class PostgresToMinioJobBuilder:
    """
    Extracts a Postgres table via NiFi and lands it as raw JSON in a MinIO
    staging bucket. That's the full extent of this pipeline's job - cleansing
    and the actual Parquet conversion happen downstream in Spark, when the
    staged batch is written into an Iceberg table (Iceberg's default file
    format is Parquet, and that write is also what registers the data in the
    Iceberg REST catalog - doing it earlier, in NiFi, would just produce
    Parquet files with no catalog metadata).

    Every property key/shape below was verified against a live NiFi 1.28.1
    instance (create -> read back descriptors -> confirm) rather than trusted
    from docs, since NiFi's internal property keys frequently diverge from
    their display names (e.g. the Record Writer property on
    QueryDatabaseTableRecord is actually named "qdbtr-record-writer").
    """

    POSTGRES_PROCESSOR_TYPE = "org.apache.nifi.processors.standard.QueryDatabaseTableRecord"
    S3_PROCESSOR_TYPE = "org.apache.nifi.processors.aws.s3.PutS3Object"
    DBCP_SERVICE_TYPE = "org.apache.nifi.dbcp.DBCPConnectionPool"
    JSON_WRITER_SERVICE_TYPE = "org.apache.nifi.json.JsonRecordSetWriter"
    AWS_CREDS_SERVICE_TYPE = (
        "org.apache.nifi.processors.aws.credentials.provider.service."
        "AWSCredentialsProviderControllerService"
    )

    STAGING_BUCKET = "staging"

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.nifi = NiFiClient()

    def build(self):

        group = self._create_process_group()
        group_id = group["id"]

        dbcp = self._create_dbcp_service(group_id)
        json_writer = self._create_json_writer_service(group_id)
        aws_creds = self._create_aws_credentials_service(group_id)

        postgres = self._create_postgres_processor(group_id)
        s3 = self._create_s3_processor(group_id)

        self._configure_postgres_processor(postgres, dbcp["id"], json_writer["id"])
        self._configure_s3_processor(s3, aws_creds["id"])

        self.nifi.create_connection(group_id, postgres["id"], s3["id"])

        for service in (dbcp, json_writer, aws_creds):
            self._enable_controller_service(service["id"])

        return {
            "process_group_id": group_id,
            "source_processor_id": postgres["id"],
            "destination_processor_id": s3["id"],
            "staging_path": f"s3a://{self.STAGING_BUCKET}/{self.pipeline.id}/data.json",
        }

    def start(self, result):
        # Destination first, so nothing produced by the source is ever routed
        # to a processor that isn't ready to receive it yet.
        self._start_processor(result["destination_processor_id"])
        self._start_processor(result["source_processor_id"])

    def stop(self, result):
        self._stop_processor(result["source_processor_id"])
        self._stop_processor(result["destination_processor_id"])

    # --------------------------------------------------
    # Process group / controller services
    # --------------------------------------------------

    def _create_process_group(self):

        root_group_id = (
            self.nifi.get_root_process_group_id()
        )

        return self.nifi.create_process_group(
            parent_process_group_id=root_group_id,
            name=self.pipeline.name,
        )

    def _create_dbcp_service(self, group_id):

        service = self.nifi.create_controller_service(
            process_group_id=group_id,
            service_type=self.DBCP_SERVICE_TYPE,
            name="Postgres Connection Pool",
        )

        config = self.pipeline.source.configuration
        jdbc_url = f"jdbc:postgresql://{config['host']}:{config['port']}/{config['database']}"

        self.nifi.update_controller_service(
            service_id=service["id"],
            revision_version=service["revision"]["version"],
            properties={
                "Database Connection URL": jdbc_url,
                "Database Driver Class Name": "org.postgresql.Driver",
                "database-driver-locations": settings.NIFI_JDBC_DRIVER_PATH,
                "Database User": config["username"],
                "Password": config["password"],
            },
        )

        return service

    def _create_json_writer_service(self, group_id):

        # Defaults (schema-access-strategy=inherit-record-schema) already do
        # the right thing for most fields. The one override needed: without
        # an explicit Timestamp Format, NiFi renders TIMESTAMP columns as
        # raw epoch-millis (confirmed live) - Spark then infers a bigint
        # instead of a real timestamp. An ISO-8601-style pattern makes
        # Spark's JSON reader infer a proper TimestampType instead.
        service = self.nifi.create_controller_service(
            process_group_id=group_id,
            service_type=self.JSON_WRITER_SERVICE_TYPE,
            name="JSON Record Writer",
        )

        self.nifi.update_controller_service(
            service_id=service["id"],
            revision_version=service["revision"]["version"],
            properties={
                "Timestamp Format": "yyyy-MM-dd'T'HH:mm:ss.SSS",
            },
        )

        return service

    def _create_aws_credentials_service(self, group_id):

        service = self.nifi.create_controller_service(
            process_group_id=group_id,
            service_type=self.AWS_CREDS_SERVICE_TYPE,
            name="MinIO Credentials",
        )

        config = self.pipeline.destination.configuration

        self.nifi.update_controller_service(
            service_id=service["id"],
            revision_version=service["revision"]["version"],
            properties={
                "Access Key": config["access_key"],
                "Secret Key": config["secret_key"],
            },
        )

        return service

    def _enable_controller_service(self, service_id):

        current = self.nifi.get_controller_service(service_id)

        self.nifi.update_controller_service_run_status(
            service_id=service_id,
            revision_version=current["revision"]["version"],
            state="ENABLED",
        )

    # --------------------------------------------------
    # Processors
    # --------------------------------------------------

    def _create_postgres_processor(self, group_id):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=self.POSTGRES_PROCESSOR_TYPE,
            name="PostgreSQL Source",
            x=0,
            y=0,
        )

    def _create_s3_processor(self, group_id):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=self.S3_PROCESSOR_TYPE,
            name="MinIO Staging Landing",
            x=400,
            y=0,
        )

    def _configure_postgres_processor(self, processor, dbcp_service_id, json_writer_service_id):

        current = self.nifi.get_processor(processor["id"])

        self.nifi.update_processor(
            processor_id=processor["id"],
            revision_version=current["revision"]["version"],
            properties={
                "Database Connection Pooling Service": dbcp_service_id,
                "Table Name": self.pipeline.source_object,
                "qdbtr-record-writer": json_writer_service_id,
                # Without this, NUMERIC/DECIMAL (and DATE/TIME/TIMESTAMP)
                # columns get written out as JSON strings (e.g.
                # "pressure":"10.58") instead of numbers - confirmed live by
                # reading a staged batch's raw JSON. Spark then infers those
                # columns as StringType, so they land as varchar in Iceberg
                # and aggregates like AVG() fail on them.
                "dbf-user-logical-types": "true",
            },
        )

        current = self.nifi.get_processor(processor["id"])

        self.nifi.set_processor_auto_terminated_relationships(
            processor_id=processor["id"],
            revision_version=current["revision"]["version"],
            relationships=["failure"],
        )

    def _configure_s3_processor(self, processor, aws_credentials_service_id):

        config = self.pipeline.destination.configuration
        current = self.nifi.get_processor(processor["id"])

        self.nifi.update_processor(
            processor_id=processor["id"],
            revision_version=current["revision"]["version"],
            properties={
                "Bucket": self.STAGING_BUCKET,
                "Object Key": f"{self.pipeline.id}/data.json",
                "Region": "us-east-1",
                "Endpoint Override URL": config["endpoint"],
                "AWS Credentials Provider service": aws_credentials_service_id,
            },
        )

        current = self.nifi.get_processor(processor["id"])

        self.nifi.set_processor_auto_terminated_relationships(
            processor_id=processor["id"],
            revision_version=current["revision"]["version"],
            relationships=["failure", "success"],
        )

    def _start_processor(self, processor_id):

        current = self.nifi.get_processor(processor_id)

        self.nifi.update_processor_run_status(
            processor_id=processor_id,
            revision_version=current["revision"]["version"],
            state="RUNNING",
        )

    def _stop_processor(self, processor_id):

        current = self.nifi.get_processor(processor_id)

        self.nifi.update_processor_run_status(
            processor_id=processor_id,
            revision_version=current["revision"]["version"],
            state="STOPPED",
        )


class KafkaToMinioJobBuilder:
    """
    Consumes a Kafka topic via NiFi and lands each message as its own raw
    JSON object in a MinIO staging prefix. No ConvertRecord/record-writer
    controller service needed here - unlike Postgres's tabular rows, Kafka
    messages (per this project's producers) already arrive as JSON, so
    ConsumeKafka_2_6's raw flowfile content is already exactly what should
    be staged. Property keys verified against a live NiFi 1.28.1 instance
    the same way as PostgresToMinioJobBuilder.
    """

    KAFKA_PROCESSOR_TYPE = "org.apache.nifi.processors.kafka.pubsub.ConsumeKafka_2_6"
    S3_PROCESSOR_TYPE = "org.apache.nifi.processors.aws.s3.PutS3Object"
    AWS_CREDS_SERVICE_TYPE = (
        "org.apache.nifi.processors.aws.credentials.provider.service."
        "AWSCredentialsProviderControllerService"
    )

    STAGING_BUCKET = "staging"

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.nifi = NiFiClient()

    def build(self):

        group = self._create_process_group()
        group_id = group["id"]

        aws_creds = self._create_aws_credentials_service(group_id)

        kafka = self._create_kafka_processor(group_id)
        s3 = self._create_s3_processor(group_id)

        self._configure_kafka_processor(kafka)
        self._configure_s3_processor(s3, aws_creds["id"])

        self.nifi.create_connection(group_id, kafka["id"], s3["id"])

        self._enable_controller_service(aws_creds["id"])

        return {
            "process_group_id": group_id,
            "source_processor_id": kafka["id"],
            "destination_processor_id": s3["id"],
            "staging_path": f"s3a://{self.STAGING_BUCKET}/{self.pipeline.id}/",
        }

    def start(self, result):
        self._start_processor(result["destination_processor_id"])
        self._start_processor(result["source_processor_id"])

    def stop(self, result):
        self._stop_processor(result["source_processor_id"])
        self._stop_processor(result["destination_processor_id"])

    # --------------------------------------------------
    # Process group / controller service
    # --------------------------------------------------

    def _create_process_group(self):

        root_group_id = (
            self.nifi.get_root_process_group_id()
        )

        return self.nifi.create_process_group(
            parent_process_group_id=root_group_id,
            name=self.pipeline.name,
        )

    def _create_aws_credentials_service(self, group_id):

        service = self.nifi.create_controller_service(
            process_group_id=group_id,
            service_type=self.AWS_CREDS_SERVICE_TYPE,
            name="MinIO Credentials",
        )

        config = self.pipeline.destination.configuration

        self.nifi.update_controller_service(
            service_id=service["id"],
            revision_version=service["revision"]["version"],
            properties={
                "Access Key": config["access_key"],
                "Secret Key": config["secret_key"],
            },
        )

        return service

    def _enable_controller_service(self, service_id):

        current = self.nifi.get_controller_service(service_id)

        self.nifi.update_controller_service_run_status(
            service_id=service_id,
            revision_version=current["revision"]["version"],
            state="ENABLED",
        )

    # --------------------------------------------------
    # Processors
    # --------------------------------------------------

    def _create_kafka_processor(self, group_id):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=self.KAFKA_PROCESSOR_TYPE,
            name="Kafka Source",
            x=0,
            y=0,
        )

    def _create_s3_processor(self, group_id):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=self.S3_PROCESSOR_TYPE,
            name="MinIO Staging Landing",
            x=400,
            y=0,
        )

    def _configure_kafka_processor(self, processor):

        config = self.pipeline.source.configuration
        bootstrap_servers = f"{config['host']}:{config['port']}"

        current = self.nifi.get_processor(processor["id"])

        self.nifi.update_processor(
            processor_id=processor["id"],
            revision_version=current["revision"]["version"],
            properties={
                "bootstrap.servers": bootstrap_servers,
                "topic": self.pipeline.source_object,
                "group.id": f"pipeline-{self.pipeline.id}",
                "security.protocol": config.get("security_protocol", "SASL_PLAINTEXT"),
                "sasl.mechanism": config.get("sasl_mechanism", "PLAIN"),
                "sasl.username": config["username"],
                "sasl.password": config["password"],
                "auto.offset.reset": "earliest",
            },
        )

        # Only relationship on this processor is "success", which is wired
        # to the S3 processor below - nothing left to auto-terminate.

    def _configure_s3_processor(self, processor, aws_credentials_service_id):

        config = self.pipeline.destination.configuration
        current = self.nifi.get_processor(processor["id"])

        self.nifi.update_processor(
            processor_id=processor["id"],
            revision_version=current["revision"]["version"],
            properties={
                "Bucket": self.STAGING_BUCKET,
                "Object Key": f"{self.pipeline.id}/${{uuid}}.json",
                "Region": "us-east-1",
                "Endpoint Override URL": config["endpoint"],
                "AWS Credentials Provider service": aws_credentials_service_id,
            },
        )

        current = self.nifi.get_processor(processor["id"])

        self.nifi.set_processor_auto_terminated_relationships(
            processor_id=processor["id"],
            revision_version=current["revision"]["version"],
            relationships=["failure", "success"],
        )

    def _start_processor(self, processor_id):

        current = self.nifi.get_processor(processor_id)

        self.nifi.update_processor_run_status(
            processor_id=processor_id,
            revision_version=current["revision"]["version"],
            state="RUNNING",
        )

    def _stop_processor(self, processor_id):

        current = self.nifi.get_processor(processor_id)

        self.nifi.update_processor_run_status(
            processor_id=processor_id,
            revision_version=current["revision"]["version"],
            state="STOPPED",
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
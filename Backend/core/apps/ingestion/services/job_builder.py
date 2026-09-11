import boto3
from django.conf import settings

from apps.ingestion.services.nifi_client import NiFiClient
from connectors.source.google_drive.connector import GoogleDriveConnector


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


class GoogleDriveToMinioJobBuilder:
    """
    Pulls one file out of a public Google Drive folder and lands it in
    MinIO. A Drive folder can hold anything, so this branches on the file:

    - Tabular (CSV/XLSX/XLS, or a Google Sheet) -> parsed and staged as
      raw JSON in the MinIO staging bucket, same staged shape as the
      NiFi-based builders, so pipeline_ingest.py's spark.read.json()
      picks it up unmodified and merges it into an Iceberg table.
    - Anything else (images, video, PDFs, archives, ...) -> copied
      through unmodified as a raw object in the destination bucket, under
      a "google-drive/<pipeline id>/<filename>" key. There's no sensible
      row-based table for a PDF or a photo, so these skip Spark/Iceberg
      entirely - PipelineService reads `ingest_mode` on the result to
      know which of the two happened.

    Unlike Postgres/Mongo/Kafka, there's no NiFi processor for the Google
    Drive REST API in this project, and building one declaratively (list
    -> fetch -> parse) would need an InvokeHTTP+ExecuteScript chain far
    more fragile than just doing the HTTP call directly in Python. So
    build() does the actual pull-and-land work itself (a Drive file fetch
    is a single bounded HTTP call, not a long-running flow worth a NiFi
    process group) - start()/stop() are no-ops kept only so
    PipelineService can call every builder through the same interface.
    """

    STAGING_BUCKET = "staging"
    RAW_FILES_PREFIX = "google-drive"

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def build(self):

        filename = self.pipeline.source_object
        connector = GoogleDriveConnector(self.pipeline.source)
        client = self._minio_client()

        if connector.is_tabular(filename):
            return self._stage_tabular(connector, filename, client)

        return self._land_raw(connector, filename, client)

    def _minio_client(self):
        config = self.pipeline.destination.configuration

        return boto3.client(
            "s3",
            endpoint_url=config["endpoint"],
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
        )

    def _stage_tabular(self, connector, filename, client):

        df = connector.read_asset(filename)

        object_key = f"{self.pipeline.id}/data.json"
        body = df.to_json(orient="records", lines=True).encode("utf-8")

        client.put_object(Bucket=self.STAGING_BUCKET, Key=object_key, Body=body)

        return {
            "process_group_id": None,
            "source_processor_id": None,
            "destination_processor_id": None,
            "ingest_mode": "table",
            "staging_path": f"s3a://{self.STAGING_BUCKET}/{object_key}",
        }

    def _land_raw(self, connector, filename, client):

        content, content_type = connector.download_raw(filename)

        config = self.pipeline.destination.configuration
        bucket = config.get("bucket") or self.STAGING_BUCKET
        object_key = f"{self.RAW_FILES_PREFIX}/{self.pipeline.id}/{filename}"

        client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=content,
            ContentType=content_type,
        )

        return {
            "process_group_id": None,
            "source_processor_id": None,
            "destination_processor_id": None,
            "ingest_mode": "file",
            "object_path": f"s3a://{bucket}/{object_key}",
        }

    def start(self, result):
        pass

    def stop(self, result):
        pass


class MongoToMinioJobBuilder:
    """
    Reads a MongoDB collection via NiFi and lands it as raw JSON in a MinIO
    staging bucket - same shape as PostgresToMinioJobBuilder (source -> S3,
    JSON, cleansing/Parquet conversion left to Spark downstream), so the
    same pipeline_ingest.py Spark script handles it unmodified.

    Every property key/shape below was verified against a live NiFi 1.28.1
    instance (create -> read back descriptors -> confirm), the same method
    used for the Postgres/Kafka builders - GetMongoRecord's and
    MongoDBControllerService's actual property keys ("mongo-uri",
    "mongo-client-service", "get-mongo-record-writer-factory", etc.) don't
    match their display names ("Mongo URI", "Client Service", "Record
    Writer"), same pattern as QueryDatabaseTableRecord's "qdbtr-record-writer".
    """

    MONGO_PROCESSOR_TYPE = "org.apache.nifi.processors.mongodb.GetMongoRecord"
    S3_PROCESSOR_TYPE = "org.apache.nifi.processors.aws.s3.PutS3Object"
    MONGO_SERVICE_TYPE = "org.apache.nifi.mongodb.MongoDBControllerService"
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

        mongo_service = self._create_mongo_service(group_id)
        json_writer = self._create_json_writer_service(group_id)
        aws_creds = self._create_aws_credentials_service(group_id)

        mongo = self._create_mongo_processor(group_id)
        s3 = self._create_s3_processor(group_id)

        self._configure_mongo_processor(mongo, mongo_service["id"], json_writer["id"])
        self._configure_s3_processor(s3, aws_creds["id"])

        self.nifi.create_connection(group_id, mongo["id"], s3["id"])

        for service in (mongo_service, json_writer, aws_creds):
            self._enable_controller_service(service["id"])

        return {
            "process_group_id": group_id,
            "source_processor_id": mongo["id"],
            "destination_processor_id": s3["id"],
            "staging_path": f"s3a://{self.STAGING_BUCKET}/{self.pipeline.id}/data.json",
        }

    def start(self, result):
        # Destination first, so nothing produced by the source is ever
        # routed to a processor that isn't ready to receive it yet.
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

    def _create_mongo_service(self, group_id):

        service = self.nifi.create_controller_service(
            process_group_id=group_id,
            service_type=self.MONGO_SERVICE_TYPE,
            name="MongoDB Connection",
        )

        config = self.pipeline.source.configuration
        auth_source = config.get("authSource", "admin")
        uri = f"mongodb://{config['host']}:{config['port']}/?authSource={auth_source}"

        self.nifi.update_controller_service(
            service_id=service["id"],
            revision_version=service["revision"]["version"],
            properties={
                "mongo-uri": uri,
                "Database User": config["username"],
                "Password": config["password"],
            },
        )

        return service

    def _create_json_writer_service(self, group_id):

        # Same override as Postgres's JSON Record Writer service, for the
        # same reason - without an explicit Timestamp Format, a Mongo Date
        # field would render as raw epoch-millis instead of parsing as a
        # real timestamp downstream in Spark.
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

    def _create_mongo_processor(self, group_id):

        return self.nifi.create_processor(
            process_group_id=group_id,
            processor_type=self.MONGO_PROCESSOR_TYPE,
            name="MongoDB Source",
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

    def _configure_mongo_processor(self, processor, mongo_service_id, json_writer_service_id):

        config = self.pipeline.source.configuration
        current = self.nifi.get_processor(processor["id"])

        self.nifi.update_processor(
            processor_id=processor["id"],
            revision_version=current["revision"]["version"],
            properties={
                "mongo-client-service": mongo_service_id,
                "get-mongo-record-writer-factory": json_writer_service_id,
                "Mongo Database Name": config["database"],
                "Mongo Collection Name": self.pipeline.source_object,
            },
        )

        current = self.nifi.get_processor(processor["id"])

        # "original" isn't meaningful for a source-only processor (there's
        # no incoming flowfile to pass through) and "failure" should just
        # not queue up - only "success" (wired to the S3 processor) is left.
        self.nifi.set_processor_auto_terminated_relationships(
            processor_id=processor["id"],
            revision_version=current["revision"]["version"],
            relationships=["failure", "original"],
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
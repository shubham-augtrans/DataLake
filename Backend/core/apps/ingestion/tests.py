from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.data_destination.models import DataDestination
from apps.data_sources.models import DataSource

from .models import IngestionPipeline, PipelineRun
from .services.pipeline_service import PipelineService

User = get_user_model()


class PipelineServiceRunTrackingTests(TestCase):
    """
    Tests the run()/PipelineRun bookkeeping contract itself - patched at
    _dispatch() so these don't depend on any one source type's NiFi/Spark
    internals (kept separate from MongoIngestionNotImplementedTests below,
    which specifically covers mongo's real current behavior).
    """

    def setUp(self):
        source = DataSource.objects.create(name="Src", source_type="postgres", configuration={})
        destination = DataDestination.objects.create(name="Dst", destination_type="minio", configuration={})
        self.pipeline = IngestionPipeline.objects.create(
            name="Test Pipeline", source=source, destination=destination, sync_interval=1,
        )

    @patch("apps.ingestion.services.pipeline_service.PipelineService._dispatch")
    def test_successful_run_creates_success_pipeline_run(self, mock_dispatch):
        mock_dispatch.return_value = {"table": "lakehouse.ingested.test"}

        PipelineService(self.pipeline).run()

        run = PipelineRun.objects.get(pipeline=self.pipeline)
        self.assertEqual(run.status, PipelineRun.Status.SUCCESS)
        self.assertEqual(run.triggered_by, "manual")
        self.assertIsNotNone(run.finished_at)

    @patch("apps.ingestion.services.pipeline_service.PipelineService._dispatch")
    def test_failed_run_creates_failed_pipeline_run(self, mock_dispatch):
        mock_dispatch.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            PipelineService(self.pipeline).run(triggered_by="airflow")

        run = PipelineRun.objects.get(pipeline=self.pipeline)
        self.assertEqual(run.status, PipelineRun.Status.FAILED)
        self.assertEqual(run.triggered_by, "airflow")
        self.assertEqual(run.message, "boom")

    @patch("apps.ingestion.services.pipeline_service.PipelineService._dispatch")
    def test_run_is_visible_as_running_mid_execution(self, mock_dispatch):
        # Simulate a slow dispatch that another request would observe as
        # still RUNNING - the PipelineRun row is created before dispatch.
        def slow_dispatch():
            self.assertEqual(
                PipelineRun.objects.get(pipeline=self.pipeline).status,
                PipelineRun.Status.RUNNING,
            )
            return {"table": "lakehouse.ingested.test"}

        mock_dispatch.side_effect = slow_dispatch
        PipelineService(self.pipeline).run()


class MongoIngestionTests(TestCase):
    """
    Mongo now follows the same start -> drain -> stop -> Spark flow as
    Postgres/Kafka (see MongoToMinioJobBuilder in job_builder.py) - these
    mock NiFiClient/run_spark_ingest the same way the Postgres/Kafka paths
    would need to, to exercise pipeline_service.py's own orchestration
    logic without touching real NiFi/Spark.
    """

    def setUp(self):
        source = DataSource.objects.create(
            name="Src", source_type="mongo",
            configuration={"host": "localhost", "port": 27017, "username": "u", "password": "p", "database": "db"},
        )
        destination = DataDestination.objects.create(
            name="Dst", destination_type="minio",
            configuration={"endpoint": "http://minio:9000", "access_key": "ak", "secret_key": "sk"},
        )
        self.pipeline = IngestionPipeline.objects.create(
            name="Mongo Pipeline", source=source, destination=destination,
            sync_interval=1, source_object="my_collection",
        )

    @patch("apps.ingestion.services.pipeline_service.time.sleep")
    @patch("apps.ingestion.services.pipeline_service.run_spark_ingest")
    @patch("apps.ingestion.services.pipeline_service.NiFiClient")
    @patch("apps.ingestion.services.pipeline_service.MongoToMinioJobBuilder")
    def test_successful_mongo_run(self, mock_builder_cls, mock_nifi_cls, mock_run_spark, mock_sleep):
        builder = mock_builder_cls.return_value
        builder.build.return_value = {
            "process_group_id": "pg1", "source_processor_id": "src1",
            "destination_processor_id": "dst1", "staging_path": "s3a://staging/1/data.json",
        }
        mock_nifi_cls.return_value.get_processor.return_value = {
            "status": {"aggregateSnapshot": {"flowFilesOut": 1}}
        }
        mock_nifi_cls.return_value.get_process_group_status.return_value = {
            "processGroupStatus": {"aggregateSnapshot": {"flowFilesQueued": 0}}
        }
        mock_run_spark.return_value = {"table": "lakehouse.ingested.my_collection"}

        result = PipelineService(self.pipeline).run()

        builder.start.assert_called_once()
        builder.stop.assert_called_once()
        mock_run_spark.assert_called_once()
        self.assertEqual(result["table"], "lakehouse.ingested.my_collection")

        self.pipeline.refresh_from_db()
        self.assertEqual(self.pipeline.nifi_status, "success")

        run = PipelineRun.objects.get(pipeline=self.pipeline)
        self.assertEqual(run.status, PipelineRun.Status.SUCCESS)

    @patch("apps.ingestion.services.pipeline_service.time.sleep")
    @patch("apps.ingestion.services.pipeline_service.run_spark_ingest")
    @patch("apps.ingestion.services.pipeline_service.NiFiClient")
    @patch("apps.ingestion.services.pipeline_service.MongoToMinioJobBuilder")
    def test_failed_mongo_spark_step_stops_processors_and_marks_error(
        self, mock_builder_cls, mock_nifi_cls, mock_run_spark, mock_sleep
    ):
        from apps.ingestion.services.spark_runner import SparkIngestError

        builder = mock_builder_cls.return_value
        builder.build.return_value = {
            "process_group_id": "pg1", "source_processor_id": "src1",
            "destination_processor_id": "dst1", "staging_path": "s3a://staging/1/data.json",
        }
        mock_nifi_cls.return_value.get_processor.return_value = {
            "status": {"aggregateSnapshot": {"flowFilesOut": 1}}
        }
        mock_nifi_cls.return_value.get_process_group_status.return_value = {
            "processGroupStatus": {"aggregateSnapshot": {"flowFilesQueued": 0}}
        }
        mock_run_spark.side_effect = SparkIngestError("spark blew up")

        with self.assertRaises(SparkIngestError):
            PipelineService(self.pipeline).run()

        # Called twice by design (once after drain, once in the except
        # block) - same pattern as the Postgres/Kafka paths; stop() is
        # idempotent so this is safe, not a bug.
        self.assertEqual(builder.stop.call_count, 2)

        self.pipeline.refresh_from_db()
        self.assertEqual(self.pipeline.nifi_status, "error")
        self.assertEqual(self.pipeline.nifi_last_error, "spark blew up")

        run = PipelineRun.objects.get(pipeline=self.pipeline)
        self.assertEqual(run.status, PipelineRun.Status.FAILED)


class PipelineRunEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="tester@example.com", password="x", phone="1234567890")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        source = DataSource.objects.create(name="Src", source_type="mongo", configuration={})
        destination = DataDestination.objects.create(name="Dst", destination_type="minio", configuration={})
        self.pipeline = IngestionPipeline.objects.create(
            name="Test Pipeline", source=source, destination=destination, sync_interval=1,
        )

    def test_running_endpoint_only_shows_running_rows(self):
        PipelineRun.objects.create(pipeline=self.pipeline, status=PipelineRun.Status.SUCCESS)
        running_run = PipelineRun.objects.create(pipeline=self.pipeline, status=PipelineRun.Status.RUNNING)

        response = self.client.get("/api/ingestion-pipelines/running/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], running_run.id)
        self.assertEqual(response.data[0]["pipeline_name"], "Test Pipeline")

    def test_runs_endpoint_shows_history(self):
        PipelineRun.objects.create(pipeline=self.pipeline, status=PipelineRun.Status.SUCCESS)
        PipelineRun.objects.create(pipeline=self.pipeline, status=PipelineRun.Status.FAILED)

        response = self.client.get("/api/ingestion-pipelines/runs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

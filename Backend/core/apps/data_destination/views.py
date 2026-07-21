from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DataDestination
from .serializers import DataDestinationSerializer


class DataDestinationViewSet(viewsets.ModelViewSet):
    queryset = DataDestination.objects.all().order_by("-created_at")
    serializer_class = DataDestinationSerializer

    @action(detail=False, methods=["get"])
    def count(self, request):
        return Response({
            "count": self.get_queryset().count()
        })

    @action(detail=False, methods=["get"], url_path="destination-types")
    def destination_types(self, request):
        return Response([
            {
                "value": value,
                "label": label,
            }
            for value, label in DataDestination.DESTINATION_TYPES
        ])

    @action(detail=True, methods=["get"])
    def configuration(self, request, pk=None):
        """
        Returns the complete destination configuration.
        """
        destination = self.get_object()

        return Response(destination.configuration)

    @action(detail=True, methods=["get"])
    def notebook(self, request, pk=None):
        """
        Returns the Jupyter Notebook URL.
        """
        destination = self.get_object()

        return Response({
            "name": destination.name,
            "url": destination.configuration.get("jupyter_url")
        })

    @action(detail=True, methods=["get"])
    def connection(self, request, pk=None):
        """
        Returns connection information required by Spark/Notebook.
        """
        destination = self.get_object()

        config = destination.configuration

        return Response({
            "engine": config.get("engine"),
            "query_engine": config.get("query_engine"),
            "catalog": config.get("catalog", {}),
            "storage": config.get("storage", {})
        })

    @action(detail=True, methods=["get"])
    def spark_config(self, request, pk=None):
        """
        Returns Spark configuration that can be consumed directly
        by a notebook or API.
        """
        destination = self.get_object()

        config = destination.configuration
        catalog = config.get("catalog", {})
        storage = config.get("storage", {})

        return Response({
            "spark.sql.catalog.demo": "org.apache.iceberg.spark.SparkCatalog",
            "spark.sql.catalog.demo.type": catalog.get("type"),
            "spark.sql.catalog.demo.uri": catalog.get("uri"),
            "spark.sql.catalog.demo.warehouse": catalog.get("warehouse"),
            "spark.sql.catalog.demo.io-impl": "org.apache.iceberg.aws.s3.S3FileIO",
            "spark.sql.catalog.demo.s3.endpoint": storage.get("endpoint"),
            "spark.sql.catalog.demo.s3.access-key-id": storage.get("access_key"),
            "spark.sql.catalog.demo.s3.secret-access-key": storage.get("secret_key"),
            "spark.sql.catalog.demo.s3.region": storage.get("region"),
        })
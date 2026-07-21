import os
import traceback
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DataSource
from .serializers import DataSourceSerializer

from connectors.source.factory import SourceConnectorFactory


class DataSourceViewSet(viewsets.ModelViewSet):
    queryset = DataSource.objects.all().order_by("-created_at")
    serializer_class = DataSourceSerializer

    @action(detail=False, methods=["get"], url_path="count")
    def count(self, request):
        return Response({
            "count": self.get_queryset().count()
        })

    @action(detail=False, methods=["get"], url_path="source-types")
    def source_types(self, request):
        return Response([
            {
                "value": value,
                "label": label,
            }
            for value, label in DataSource.SOURCE_TYPES
        ])

    @action(detail=True, methods=["get"], url_path="check-connection")
    def check_connection(self, request, pk=None):

        datasource = self.get_object()

        try:
            connector = SourceConnectorFactory.get_connector(datasource)

            buckets = connector.check_connection()

            return Response({
                "connected": True,
                "buckets": [
                    bucket["Name"]
                    for bucket in buckets.get("Buckets", [])
                ]
            })

        except Exception as ex:
            traceback.print_exc() 
            return Response(
                {
                    "connected": False,
                    "error": str(ex)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"], url_path="list-buckets")
    def list_buckets(self, request, pk=None):

        datasource = self.get_object()

        try:
            connector = SourceConnectorFactory.get_connector(datasource)

            buckets = connector.list_buckets()

            return Response(buckets)

        except Exception as ex:
            return Response(
                {"error": str(ex)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"], url_path="list-assets")
    def list_assets(self, request, pk=None):

        datasource = self.get_object()

        bucket = request.query_params.get("bucket")

        if not bucket:
            return Response(
                {
                    "error": "bucket query parameter is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            connector = SourceConnectorFactory.get_connector(datasource)

            assets = connector.list_assets(bucket)

            files = []

            for asset in assets:

                filename = asset["Key"]

                files.append({
                    "name": filename,
                    "type": os.path.splitext(filename)[1].lstrip("."),
                    "size": asset["Size"],
                    "last_modified": asset["LastModified"],
                })

            return Response(files)

        except Exception as ex:
            return Response(
                {"error": str(ex)},
                status=status.HTTP_400_BAD_REQUEST,
            )
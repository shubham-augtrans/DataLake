from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import IcebergCatalogClient, IcebergCatalogError


class NamespaceListView(APIView):

    def get(self, request):
        try:
            namespaces = IcebergCatalogClient().list_namespaces()
            return Response({"namespaces": namespaces})

        except IcebergCatalogError as ex:
            return Response(
                {"error": str(ex)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class TableListView(APIView):

    def get(self, request):
        namespace = request.query_params.get("namespace")

        if not namespace:
            return Response(
                {"error": "namespace query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tables = IcebergCatalogClient().list_tables(namespace)
            return Response({"namespace": namespace, "tables": tables})

        except IcebergCatalogError as ex:
            return Response(
                {"error": str(ex)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class TableDetailView(APIView):

    def get(self, request):
        namespace = request.query_params.get("namespace")
        table = request.query_params.get("table")

        if not namespace or not table:
            return Response(
                {"error": "namespace and table query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            detail = IcebergCatalogClient().get_table(namespace, table)
            return Response(detail)

        except IcebergCatalogError as ex:
            return Response(
                {"error": str(ex)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

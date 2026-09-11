from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DataDictionaryEntry
from .permissions import CanEditDataDictionary
from .serializers import DataDictionaryEntrySerializer, DataDictionaryUpsertSerializer
from .services import IcebergCatalogClient, IcebergCatalogError


class NamespaceListView(APIView):

    permission_classes = [IsAuthenticated]

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

    permission_classes = [IsAuthenticated]

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

    permission_classes = [IsAuthenticated]

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

        except IcebergCatalogError as ex:
            return Response(
                {"error": str(ex)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        entries = DataDictionaryEntry.objects.filter(namespace=namespace, table_name=table)
        column_descriptions = {}
        table_description = ""

        for entry in entries:
            if entry.column_name:
                column_descriptions[entry.column_name] = entry.description
            else:
                table_description = entry.description

        detail["description"] = table_description
        for column in detail.get("columns", []):
            column["description"] = column_descriptions.get(column.get("name"), "")

        return Response(detail)


class DataDictionaryView(APIView):
    """
    Business-meaning layer on top of Iceberg's structural metadata: lets
    admins/data engineers document what a table or column actually holds,
    surfaced to every user browsing the catalog or writing SQL.
    """

    def get_permissions(self):
        if self.request.method in ("PUT", "DELETE"):
            return [IsAuthenticated(), CanEditDataDictionary()]
        return [IsAuthenticated()]

    def get(self, request):
        namespace = request.query_params.get("namespace")
        table = request.query_params.get("table")

        if not namespace or not table:
            return Response(
                {"error": "namespace and table query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entries = DataDictionaryEntry.objects.filter(namespace=namespace, table_name=table)
        serializer = DataDictionaryEntrySerializer(entries, many=True)
        return Response(serializer.data)

    def put(self, request):
        serializer = DataDictionaryUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        column_name = (data.get("column") or "").strip()

        entry, _ = DataDictionaryEntry.objects.update_or_create(
            namespace=data["namespace"],
            table_name=data["table"],
            column_name=column_name,
            defaults={
                "description": data["description"],
                "updated_by": request.user,
            },
        )

        return Response(
            DataDictionaryEntrySerializer(entry).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        namespace = request.query_params.get("namespace")
        table = request.query_params.get("table")
        column = request.query_params.get("column", "")

        if not namespace or not table:
            return Response(
                {"error": "namespace and table query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        DataDictionaryEntry.objects.filter(
            namespace=namespace, table_name=table, column_name=column
        ).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

import requests
from django.conf import settings

REQUEST_TIMEOUT = 10


class IcebergCatalogError(Exception):
    pass


class IcebergCatalogClient:
    """
    Thin client over the Iceberg REST Catalog's own HTTP API
    (https://iceberg.apache.org/rest-catalog-spec/). No pyiceberg/JVM
    dependency needed - the REST fixture already speaks plain JSON.
    """

    def __init__(self):
        self.base_url = settings.ICEBERG_REST_URL.rstrip("/")

    def _get(self, path):
        try:
            response = requests.get(f"{self.base_url}{path}", timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()

        except requests.RequestException as ex:
            raise IcebergCatalogError(f"Failed to reach Iceberg REST catalog: {str(ex)}")

    def list_namespaces(self):
        data = self._get("/v1/namespaces")

        return [".".join(parts) for parts in data.get("namespaces", [])]

    def list_tables(self, namespace):
        data = self._get(f"/v1/namespaces/{namespace}/tables")

        return [
            identifier["name"]
            for identifier in data.get("identifiers", [])
        ]

    def get_table(self, namespace, table):
        data = self._get(f"/v1/namespaces/{namespace}/tables/{table}")
        metadata = data.get("metadata", {})

        schemas = metadata.get("schemas", [])
        current_schema_id = metadata.get("current-schema-id", 0)
        current_schema = next(
            (s for s in schemas if s.get("schema-id") == current_schema_id),
            schemas[0] if schemas else {},
        )

        columns = [
            {
                "name": field.get("name"),
                "type": field.get("type"),
                "required": field.get("required", False),
            }
            for field in current_schema.get("fields", [])
        ]

        snapshots = metadata.get("snapshots", [])
        current_snapshot_id = metadata.get("current-snapshot-id")
        current_snapshot = next(
            (s for s in snapshots if s.get("snapshot-id") == current_snapshot_id),
            None,
        )

        summary = (current_snapshot or {}).get("summary", {})

        return {
            "namespace": namespace,
            "table": table,
            "location": metadata.get("location"),
            "columns": columns,
            "snapshot_count": len(snapshots),
            "current_snapshot_id": current_snapshot_id,
            "total_records": summary.get("total-records"),
            "total_data_files": summary.get("total-data-files"),
            "last_updated_ms": metadata.get("last-updated-ms"),
        }

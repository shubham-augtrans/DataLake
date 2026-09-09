import requests
from django.conf import settings

from apps.query.services import LAKEHOUSE_SCHEMA

CHART_TO_DISPLAY = {
    "bar": "bar",
    "line": "line",
    "number": "scalar",
    "table": "table",
    "pie": "pie",
}

DEFAULT_SIZE_X = 12
DEFAULT_SIZE_Y = 8
GRID_COLUMNS = 2


class MetabaseError(Exception):
    pass


class MetabaseClient:
    """
    Thin wrapper around the Metabase REST API used to turn a Playground
    prompt into a real, visible Metabase dashboard (Cards + a Dashboard),
    rather than a chart rendered locally.
    """

    def __init__(self):
        if not settings.METABASE_API_KEY:
            raise MetabaseError("METABASE_API_KEY is not configured.")

        self.base_url = settings.METABASE_URL.rstrip("/")

        self.session = requests.Session()
        self.session.headers.update({"x-api-key": settings.METABASE_API_KEY})

    def _url(self, path):
        return f"{self.base_url}/{path.lstrip('/')}"

    def _get(self, path, **kwargs):
        response = self.session.get(self._url(path), timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def _post(self, path, data=None, **kwargs):
        response = self.session.post(self._url(path), json=data, timeout=30, **kwargs)

        if not response.ok:
            raise MetabaseError(
                f"Metabase API error {response.status_code}: {response.text}"
            )

        return response.json() if response.content else None

    def _put(self, path, data=None, **kwargs):
        response = self.session.put(self._url(path), json=data, timeout=30, **kwargs)

        if not response.ok:
            raise MetabaseError(
                f"Metabase API error {response.status_code}: {response.text}"
            )

        return response.json() if response.content else None

    def chart_to_display(self, chart_type):
        return CHART_TO_DISPLAY.get(chart_type, "table")

    LAKEHOUSE_DATABASE_NAME = "Lakehouse (Trino)"

    def find_or_create_lakehouse_database_id(self):
        """
        Metabase's own connection to the lakehouse (Iceberg tables on MinIO,
        queried through Trino) - there's exactly one of these, shared by
        every Playground dashboard, unlike the old per-DataSource Postgres
        lookup. Metabase's "starburst" driver speaks Trino's wire protocol.
        Uses TRINO_INTERNAL_HOST/PORT since Metabase - a container - can't
        reach Trino via the host-mapped port Django uses.
        """
        result = self._get("/api/database")
        databases = result.get("data", result) if isinstance(result, dict) else result

        for db in databases:
            if db.get("name") == self.LAKEHOUSE_DATABASE_NAME:
                return db["id"]

        created = self._post("/api/database", {
            "name": self.LAKEHOUSE_DATABASE_NAME,
            "engine": "starburst",
            "details": {
                "host": settings.TRINO_INTERNAL_HOST,
                "port": settings.TRINO_INTERNAL_PORT,
                "catalog": settings.TRINO_CATALOG,
                # Without a default schema, Metabase's own query execution
                # can't resolve the unqualified table names the LLM
                # generates (Trino error: "Schema must be specified when
                # session schema is not set") - even though the same SQL
                # works fine through Django's TrinoQueryRunner, which sets
                # this explicitly on its own connection.
                "schema": LAKEHOUSE_SCHEMA,
                "user": settings.TRINO_METABASE_USER,
                "ssl": False,
            },
        })

        return created["id"]

    def create_card(self, database_id, name, sql, display, collection_id=None):
        payload = {
            "name": name,
            "display": display,
            "visualization_settings": {},
            "collection_id": collection_id,
            "dataset_query": {
                "type": "native",
                "native": {"query": sql},
                "database": database_id,
            },
        }

        return self._post("/api/card", payload)

    def create_dashboard(self, name, collection_id=None):
        return self._post("/api/dashboard", {"name": name, "collection_id": collection_id})

    def add_cards_to_dashboard(self, dashboard_id, card_ids):
        """
        Lay out `card_ids` two-per-row on the dashboard's grid and attach them
        in one bulk call, using Metabase's modern PUT /api/dashboard/:id/cards
        (verified against this project's live v0.63.13 instance).
        """
        cards = []

        for index, card_id in enumerate(card_ids):
            row = (index // GRID_COLUMNS) * DEFAULT_SIZE_Y
            col = (index % GRID_COLUMNS) * DEFAULT_SIZE_X

            cards.append({
                "id": -(index + 1),
                "card_id": card_id,
                "row": row,
                "col": col,
                "size_x": DEFAULT_SIZE_X,
                "size_y": DEFAULT_SIZE_Y,
            })

        return self._put(f"/api/dashboard/{dashboard_id}/cards", {"cards": cards})

    def dashboard_url(self, dashboard_id):
        return f"{self.base_url}/dashboard/{dashboard_id}"

    def create_public_link(self, dashboard_id):
        """
        Mints a public, unauthenticated link for the dashboard so it can be
        embedded in an <iframe> in the app. Requires the "Public Sharing"
        setting to be turned on in Metabase Admin (a security setting this
        app deliberately never toggles on its own).
        """
        try:
            result = self._post(f"/api/dashboard/{dashboard_id}/public_link")
        except MetabaseError as ex:
            raise MetabaseError(
                f"Could not create a public link ({ex}). "
                "Enable 'Public Sharing' in Metabase Admin -> Settings first."
            )

        return f"{self.base_url}/public/dashboard/{result['uuid']}"

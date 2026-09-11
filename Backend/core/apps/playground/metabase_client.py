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

    def update_card(self, card_id, sql, database_id, display):
        """
        Rewrites an existing card's query and chart type in place, instead of
        creating a new card - used when the user asks to re-render the same
        data differently ("same data as a pie chart") so the dashboard
        already on screen updates rather than a second one appearing.
        """
        payload = {
            "display": display,
            "dataset_query": {
                "type": "native",
                "native": {"query": sql},
                "database": database_id,
            },
        }

        return self._put(f"/api/card/{card_id}", payload)

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

    def append_card_to_dashboard(self, dashboard_id, card_id, row=None, col=None):
        """
        Adds a new card to a dashboard alongside whatever's already on it
        (instead of replacing anything) - used when the user asks to add a
        chart to the dashboard already on screen rather than replace it.
        Pass `row`/`col` to place it at a specific grid position (e.g.
        "beside" or "below" another card, resolved by
        services.resolve_relative_layout); omit both for the default
        next-open-slot placement.
        """
        dashboard = self._get(f"/api/dashboard/{dashboard_id}")
        existing = dashboard.get("dashcards", [])

        cards = [
            {
                "id": dashcard["id"],
                "card_id": dashcard["card_id"],
                "row": dashcard["row"],
                "col": dashcard["col"],
                "size_x": dashcard["size_x"],
                "size_y": dashcard["size_y"],
            }
            for dashcard in existing
        ]

        if row is None or col is None:
            index = len(cards)
            row = (index // GRID_COLUMNS) * DEFAULT_SIZE_Y
            col = (index % GRID_COLUMNS) * DEFAULT_SIZE_X

        cards.append({
            "id": -(len(cards) + 1),
            "card_id": card_id,
            "row": row,
            "col": col,
            "size_x": DEFAULT_SIZE_X,
            "size_y": DEFAULT_SIZE_Y,
        })

        return self._put(f"/api/dashboard/{dashboard_id}/cards", {"cards": cards})

    def remove_card_from_dashboard(self, dashboard_id, card_id):
        """
        Detaches a card from a dashboard (the other cards keep their
        positions) and archives the card itself, so "delete that chart"
        actually removes it rather than leaving an orphaned card behind.
        """
        dashboard = self._get(f"/api/dashboard/{dashboard_id}")
        existing = dashboard.get("dashcards", [])

        cards = [
            {
                "id": dashcard["id"],
                "card_id": dashcard["card_id"],
                "row": dashcard["row"],
                "col": dashcard["col"],
                "size_x": dashcard["size_x"],
                "size_y": dashcard["size_y"],
            }
            for dashcard in existing
            if dashcard["card_id"] != card_id
        ]

        self._put(f"/api/dashboard/{dashboard_id}/cards", {"cards": cards})
        return self.archive_card(card_id)

    def archive_card(self, card_id):
        return self._put(f"/api/card/{card_id}", {"archived": True})

    def duplicate_card(self, card_id, database_id):
        """
        Copies an existing card's query/type into a brand-new card - used
        for "duplicate this chart" where the data must be IDENTICAL, not
        regenerated by the LLM (which could subtly drift from the original).
        """
        source = self.get_card(card_id)

        dataset_query = source.get("dataset_query", {})
        stages = dataset_query.get("stages")
        sql = stages[-1].get("native") if stages else dataset_query.get("native", {}).get("query")

        return self.create_card(
            database_id=database_id,
            name=f"{source.get('name', 'Chart')} (copy)",
            sql=sql,
            display=source.get("display", "table"),
        )

    def get_dashboard(self, dashboard_id):
        return self._get(f"/api/dashboard/{dashboard_id}")

    def get_dashboard_cards_summary(self, dashboard_id):
        """
        [{card_id, name, display, row, col, size_x, size_y}, ...] for the
        cards currently on a dashboard, in on-screen order (row then col) -
        used to let the user refer to a chart by name ("the pressure chart")
        or position ("the second chart") in a follow-up message.
        """
        dashboard = self.get_dashboard(dashboard_id)
        dashcards = dashboard.get("dashcards", [])

        summary = [
            {
                "card_id": dc["card_id"],
                "name": (dc.get("card") or {}).get("name", ""),
                "display": (dc.get("card") or {}).get("display", ""),
                "row": dc["row"],
                "col": dc["col"],
                "size_x": dc["size_x"],
                "size_y": dc["size_y"],
            }
            for dc in dashcards
        ]
        summary.sort(key=lambda c: (c["row"], c["col"]))
        return summary

    def rename_card(self, card_id, name):
        return self._put(f"/api/card/{card_id}", {"name": name})

    def get_card(self, card_id):
        return self._get(f"/api/card/{card_id}")

    def update_card_visualization_settings(self, card_id, settings_patch):
        """
        Merges `settings_patch` into whatever visualization_settings the
        card already has (colors, etc.) instead of replacing them wholesale,
        so an unrelated earlier customization isn't wiped out.
        """
        current = self.get_card(card_id)
        merged = {**(current.get("visualization_settings") or {}), **settings_patch}
        return self._put(f"/api/card/{card_id}", {"visualization_settings": merged})

    def update_dashcard_layout(self, dashboard_id, layout_by_card_id):
        """
        Repositions/resizes one or more cards already on a dashboard in a
        single PUT - `layout_by_card_id` is {card_id: {row?, col?, size_x?,
        size_y?}}; any card not mentioned keeps its current layout.
        """
        dashboard = self.get_dashboard(dashboard_id)
        existing = dashboard.get("dashcards", [])

        cards = []
        for dc in existing:
            patch = layout_by_card_id.get(dc["card_id"], {})
            cards.append({
                "id": dc["id"],
                "card_id": dc["card_id"],
                "row": patch.get("row", dc["row"]),
                "col": patch.get("col", dc["col"]),
                "size_x": patch.get("size_x", dc["size_x"]),
                "size_y": patch.get("size_y", dc["size_y"]),
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

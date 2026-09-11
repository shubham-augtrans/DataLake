import json
import re
import uuid

import requests
from django.conf import settings

from apps.query.services import LAKEHOUSE_SCHEMA

# Superset's viz_type identifiers, mapped from the same internal chart-type
# vocabulary MetabaseClient.CHART_TO_DISPLAY already uses, so views.py can
# call chart_to_display() on either client without caring which one it got.
CHART_TO_DISPLAY = {
    "bar": "echarts_timeseries_bar",
    "line": "echarts_timeseries_line",
    "number": "big_number_total",
    "table": "table",
    "pie": "pie",
}

# Metabase's dashboard grid is 24 columns wide; every row/col/size_x/size_y
# value that flows through views.py (resolve_relative_layout, the MIN/MAX
# clamps, etc.) is expressed in that 24-unit space. Superset's own dashboard
# grid is 12 columns wide, so SupersetClient accepts/returns coordinates in
# Metabase's 24-unit space (same public contract as MetabaseClient) and
# rescales internally when talking to Superset's json_metadata layout tree.
METABASE_GRID_COLUMNS = 24
SUPERSET_GRID_COLUMNS = 12
GRID_SCALE = SUPERSET_GRID_COLUMNS / METABASE_GRID_COLUMNS

# Superset's row-height grid unit is much finer than Metabase's size_y
# (confirmed live: a native single-chart dashboard saved with size_y=8
# equivalent came back as height:50) - scale so DEFAULT_SIZE_Y maps to
# that same 50, otherwise charts render as an near-invisible sliver.
HEIGHT_SCALE = 50 / 8

DEFAULT_SIZE_X = 12
DEFAULT_SIZE_Y = 8
GRID_COLUMNS = 2


class SupersetError(Exception):
    pass


class SupersetClient:
    """
    Thin wrapper around the Superset REST API, mirroring MetabaseClient's
    public method names/signatures so apps/playground/views.py can use
    either backend interchangeably via _get_bi_client(). Superset has no
    single "card" object like Metabase - a chart's data source is always a
    Dataset, so create_card/update_card do a dataset upsert + chart
    upsert under the hood; every other method maps onto Superset's
    dashboard/chart/dataset endpoints.

    Known simplification: every chart is rendered as a Superset "table"
    viz (viz_type left as requested on the chart's name/metadata for a
    later enhancement) rather than attempting to auto-infer per-viz-type
    metrics/groupby from arbitrary generated SQL - a table always renders
    correctly regardless of the result shape, whereas a wrong metric/
    groupby guess for e.g. echarts_timeseries_bar would silently render
    broken. See README for the full list of Superset-parity trade-offs.
    """

    LAKEHOUSE_DATABASE_NAME = "Lakehouse (Trino)"

    def __init__(self):
        if not settings.SUPERSET_USERNAME or not settings.SUPERSET_PASSWORD:
            raise SupersetError("SUPERSET_USERNAME / SUPERSET_PASSWORD are not configured.")

        self.base_url = settings.SUPERSET_URL.rstrip("/")
        self.session = requests.Session()
        self._authed = False

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    def _url(self, path):
        return f"{self.base_url}/{path.lstrip('/')}"

    def _login(self):
        """
        Logs in through Superset's web session form, not just the REST
        /api/v1/security/login JWT endpoint. Discovered live: Superset's
        DAO/ownership/row-level-security layer (chart owner assignment,
        the database list's access filter, etc.) reads flask_login's
        current_user, which a bare JWT Bearer token never populates in
        this Superset version - every such call silently treats the
        request as anonymous (zero results, or a crash trying to attach
        an anonymous user as a chart owner). A real session cookie from
        the login form fixes all of those at once.
        """
        login_page = self.session.get(self._url("/login/"), timeout=30)
        csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', login_page.text)
        form_csrf = csrf_match.group(1) if csrf_match else None

        response = self.session.post(
            self._url("/login/"),
            data={
                "username": settings.SUPERSET_USERNAME,
                "password": settings.SUPERSET_PASSWORD,
                "csrf_token": form_csrf,
            },
            timeout=30,
        )
        if not response.ok or response.url.rstrip("/").endswith("/login"):
            raise SupersetError(f"Superset session login failed (status {response.status_code}).")

        csrf_response = self.session.get(self._url("/api/v1/security/csrf_token/"), timeout=30)
        if not csrf_response.ok:
            raise SupersetError(
                f"Superset CSRF token fetch failed {csrf_response.status_code}: {csrf_response.text}"
            )

        csrf_token = csrf_response.json()["result"]
        self.session.headers.update({
            "X-CSRFToken": csrf_token,
            "Referer": self.base_url,
        })
        self._authed = True

    def _request(self, method, path, data=None, **kwargs):
        if not self._authed:
            self._login()

        response = self.session.request(method, self._url(path), json=data, timeout=30, **kwargs)

        if response.status_code == 401 and self._authed:
            # Access token expired mid-session - re-auth once, then retry.
            self._authed = False
            self._login()
            response = self.session.request(method, self._url(path), json=data, timeout=30, **kwargs)

        if not response.ok:
            raise SupersetError(f"Superset API error {response.status_code}: {response.text}")

        return response.json() if response.content else None

    def _get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    def _post(self, path, data=None, **kwargs):
        return self._request("POST", path, data=data, **kwargs)

    def _put(self, path, data=None, **kwargs):
        return self._request("PUT", path, data=data, **kwargs)

    def _delete(self, path, **kwargs):
        return self._request("DELETE", path, **kwargs)

    # ------------------------------------------------------------------
    # Public API - mirrors MetabaseClient
    # ------------------------------------------------------------------

    def chart_to_display(self, chart_type):
        return CHART_TO_DISPLAY.get(chart_type, "table")

    def find_or_create_lakehouse_database_id(self):
        # Fetched unfiltered and matched client-side, same as
        # MetabaseClient does - Superset's REST filter syntax (rison) needs
        # careful encoding of spaces/parens in the database name, which
        # isn't worth the fragility for a handful of databases.
        result = self._get("/api/v1/database/?q=(page_size:100)")
        for db in result.get("result", []):
            if db.get("database_name") == self.LAKEHOUSE_DATABASE_NAME:
                return db["id"]

        uri = (
            f"trino://{settings.TRINO_METABASE_USER}@"
            f"{settings.TRINO_INTERNAL_HOST}:{settings.TRINO_INTERNAL_PORT}/"
            f"{settings.TRINO_CATALOG}/{LAKEHOUSE_SCHEMA}"
        )
        try:
            created = self._post("/api/v1/database/", {
                "database_name": self.LAKEHOUSE_DATABASE_NAME,
                "sqlalchemy_uri": uri,
                "expose_in_sqllab": True,
            })
        except SupersetError as ex:
            if "already exists" not in str(ex):
                raise
            # Lost a race with another request that created it first (or
            # the page_size:100 listing above didn't include it) - fetch
            # its id instead of failing the whole operation.
            result = self._get("/api/v1/database/?q=(page_size:100)")
            for db in result.get("result", []):
                if db.get("database_name") == self.LAKEHOUSE_DATABASE_NAME:
                    return db["id"]
            raise

        return created["id"]

    def _upsert_dataset(self, database_id, name, sql, dataset_id=None):
        """
        A Superset chart's datasource is always a Dataset, never raw SQL
        directly - this creates/updates a "virtual" dataset (SQL-backed,
        not a physical table) that mirrors what a Metabase native card's
        `dataset_query.native.query` already does.
        """
        if dataset_id:
            payload = {"database": database_id, "schema": LAKEHOUSE_SCHEMA, "sql": sql}
            return self._put(f"/api/v1/dataset/{dataset_id}", payload)["id"]

        # table_name must be unique per (database, schema) - it's an
        # internal identifier, never shown to the user (the chart's own
        # slice_name is what's visible), so a uuid suffix avoids collisions
        # between two charts sharing a prompt/title, or between retries of
        # a request that partially succeeded.
        table_name = f"{name[:40]}__{uuid.uuid4().hex[:8]}"
        payload = {
            "database": database_id,
            "schema": LAKEHOUSE_SCHEMA,
            "table_name": table_name,
            "sql": sql,
        }
        return self._post("/api/v1/dataset/", payload)["id"]

    def create_card(self, database_id, name, sql, display, collection_id=None):
        dataset_id = self._upsert_dataset(database_id, name, sql)

        chart = self._post("/api/v1/chart/", {
            "slice_name": name,
            "viz_type": display,
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": self._chart_params(dataset_id, display),
            # Without this, Superset's CreateChartCommand defaults owners to
            # flask_login's current_user - which is AnonymousUserMixin under
            # our Bearer-token auth (no session cookie), and crashes trying
            # to attach an anonymous user as an ORM-mapped owner.
            "owners": [],
        })
        return {"id": chart["id"], "dataset_id": dataset_id}

    def update_card(self, card_id, sql, database_id, display):
        chart = self.get_card(card_id)
        dataset_id = chart["result"]["datasource_id"]
        self._upsert_dataset(database_id, chart["result"]["slice_name"], sql, dataset_id=dataset_id)
        return self._put(f"/api/v1/chart/{card_id}", {
            "viz_type": display,
            "params": self._chart_params(dataset_id, display),
        })

    def _table_params(self, dataset_id):
        """
        A "table" viz in raw-records mode needs an explicit column list
        (`all_columns`) - without it Superset builds an empty SELECT and
        every chart on the dashboard fails with "Empty query?" (found live:
        even Superset's own drag-and-drop UI hits this on a chart created
        via the API without it). Reads the virtual dataset's own columns
        back so every column the generated SQL selects is included.
        """
        dataset = self._get(f"/api/v1/dataset/{dataset_id}")["result"]
        columns = [c["column_name"] for c in dataset.get("columns", [])]
        return json.dumps({
            "viz_type": "table",
            "query_mode": "raw",
            "all_columns": columns,
            "row_limit": 1000,
        })

    def _chart_params(self, dataset_id, viz_type):
        """
        Builds the right `params` shape for the requested viz_type from the
        virtual dataset's own columns - the generated SQL already does the
        grouping/aggregation (e.g. "GROUP BY machine_name"), so the first
        column is treated as the dimension (x-axis/groupby) and every
        numeric column after it as a metric, aggregated with MAX (a no-op
        given one row per dimension value already, just satisfying viz
        types that require SOME aggregate function).
        """
        dataset = self._get(f"/api/v1/dataset/{dataset_id}")["result"]
        columns = dataset.get("columns", [])

        if viz_type == "table" or not columns:
            return self._table_params(dataset_id)

        dimension = columns[0]["column_name"]
        # type_generic: 0=numeric, 1=string, 2=temporal (Superset's
        # GenericDataType) - confirmed live against a Trino-backed dataset.
        metric_columns = [c["column_name"] for c in columns[1:] if c.get("type_generic") == 0] \
            or [c["column_name"] for c in columns[1:]]

        if not metric_columns:
            return self._table_params(dataset_id)

        def metric(col):
            return {
                "expressionType": "SIMPLE",
                "column": {"column_name": col},
                "aggregate": "MAX",
                "label": col,
            }

        if viz_type == "big_number_total":
            return json.dumps({
                "viz_type": viz_type,
                "metric": metric(metric_columns[0]),
                "adhoc_filters": [],
            })

        if viz_type == "pie":
            return json.dumps({
                "viz_type": viz_type,
                "groupby": [dimension],
                "metric": metric(metric_columns[0]),
                "adhoc_filters": [],
                "row_limit": 1000,
            })

        # bar/line (echarts_timeseries_bar / echarts_timeseries_line)
        return json.dumps({
            "viz_type": viz_type,
            "x_axis": dimension,
            "x_axis_sort_series": "name",
            "x_axis_sort_series_ascending": True,
            "groupby": [],
            "metrics": [metric(c) for c in metric_columns],
            "adhoc_filters": [],
            "row_limit": 1000,
            "order_desc": True,
        })

    def create_dashboard(self, name, collection_id=None):
        return self._post("/api/v1/dashboard/", {"dashboard_title": name, "owners": []})

    # ------------------------------------------------------------------
    # Dashboard layout - Superset stores the whole grid as a single nested
    # tree in its own top-level `position_json` field (NOT inside
    # json_metadata, which holds unrelated config like color_scheme/
    # chart_configuration - confirmed live by saving a real dashboard from
    # Superset's own drag-and-drop builder and reading it back via the
    # API). Build/parse a minimal tree: ROOT -> GRID -> one ROW per
    # distinct `row` value -> one CHART node per card, ordered by `col`.
    # Every node needs a `parents` chain and a `meta.background` on ROW
    # nodes - without them the dashboard view crashes (observed live:
    # "Cannot read properties of undefined (reading 'background')").
    # ------------------------------------------------------------------

    def _build_positions(self, cards, title="Dashboard"):
        positions = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
            "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": title}},
        }

        rows = {}
        for card in cards:
            rows.setdefault(card["row"], []).append(card)

        for row_key in sorted(rows.keys()):
            row_id = f"ROW-{row_key}"
            positions["GRID_ID"]["children"].append(row_id)
            row_children = []

            for card in sorted(rows[row_key], key=lambda c: c["col"]):
                chart_node_id = f"CHART-{card['card_id']}"
                row_children.append(chart_node_id)
                positions[chart_node_id] = {
                    "type": "CHART",
                    "id": chart_node_id,
                    "children": [],
                    "parents": ["ROOT_ID", "GRID_ID", row_id],
                    "meta": {
                        "chartId": card["card_id"],
                        "width": max(1, round(card["size_x"] * GRID_SCALE)),
                        "height": max(1, round(card["size_y"] * HEIGHT_SCALE)),
                        "uuid": str(uuid.uuid4()),
                    },
                }

            positions[row_id] = {
                "type": "ROW",
                "id": row_id,
                "children": row_children,
                "parents": ["ROOT_ID", "GRID_ID"],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }

        return positions

    def _parse_positions(self, positions):
        """
        Inverse of _build_positions: reconstructs {card_id, row, col,
        size_x, size_y} from a dashboard's stored layout tree. `row`/`col`
        are re-derived from tree order (row index / column index within
        row) rather than persisted pixel offsets, since that's all
        _build_positions itself encodes.
        """
        grid = positions.get("GRID_ID", {})
        summary = []

        for row_index, row_id in enumerate(grid.get("children", [])):
            row_node = positions.get(row_id, {})
            for col_index, chart_node_id in enumerate(row_node.get("children", [])):
                chart_node = positions.get(chart_node_id, {})
                meta = chart_node.get("meta", {})
                if "chartId" not in meta:
                    continue
                summary.append({
                    "card_id": meta["chartId"],
                    "row": row_index * DEFAULT_SIZE_Y,
                    "col": col_index * DEFAULT_SIZE_X,
                    "size_x": round(meta.get("width", SUPERSET_GRID_COLUMNS) / GRID_SCALE),
                    "size_y": max(1, round(meta.get("height", DEFAULT_SIZE_Y * HEIGHT_SCALE) / HEIGHT_SCALE)),
                })

        return summary

    def add_cards_to_dashboard(self, dashboard_id, card_ids):
        cards = []
        for index, card_id in enumerate(card_ids):
            row = (index // GRID_COLUMNS) * DEFAULT_SIZE_Y
            col = (index % GRID_COLUMNS) * DEFAULT_SIZE_X
            cards.append({"card_id": card_id, "row": row, "col": col, "size_x": DEFAULT_SIZE_X, "size_y": DEFAULT_SIZE_Y})

        return self._write_layout(dashboard_id, cards)

    def append_card_to_dashboard(self, dashboard_id, card_id, row=None, col=None):
        existing = self.get_dashboard_cards_summary(dashboard_id)

        if row is None or col is None:
            index = len(existing)
            row = (index // GRID_COLUMNS) * DEFAULT_SIZE_Y
            col = (index % GRID_COLUMNS) * DEFAULT_SIZE_X

        existing.append({"card_id": card_id, "row": row, "col": col, "size_x": DEFAULT_SIZE_X, "size_y": DEFAULT_SIZE_Y})
        return self._write_layout(dashboard_id, existing)

    def remove_card_from_dashboard(self, dashboard_id, card_id):
        existing = [c for c in self.get_dashboard_cards_summary(dashboard_id) if c["card_id"] != card_id]
        self._write_layout(dashboard_id, existing)
        return self.archive_card(card_id)

    def archive_card(self, card_id):
        return self._delete(f"/api/v1/chart/{card_id}")

    def duplicate_card(self, card_id, database_id):
        source = self.get_card(card_id)["result"]
        dataset = self._get(f"/api/v1/dataset/{source['datasource_id']}")["result"]
        return self.create_card(
            database_id=database_id,
            name=f"{source.get('slice_name', 'Chart')} (copy)",
            sql=dataset.get("sql", ""),
            display="table",
        )

    def get_dashboard(self, dashboard_id):
        return self._get(f"/api/v1/dashboard/{dashboard_id}")["result"]

    def get_dashboard_cards_summary(self, dashboard_id):
        dashboard = self.get_dashboard(dashboard_id)
        raw_positions = dashboard.get("position_json") or "{}"
        positions = json.loads(raw_positions) if isinstance(raw_positions, str) else (raw_positions or {})

        summary = self._parse_positions(positions)

        for card in summary:
            try:
                chart = self.get_card(card["card_id"])["result"]
                card["name"] = chart.get("slice_name", "")
                card["display"] = chart.get("viz_type", "")
            except SupersetError:
                card["name"] = ""
                card["display"] = ""

        summary.sort(key=lambda c: (c["row"], c["col"]))
        return summary

    def _write_layout(self, dashboard_id, cards):
        dashboard = self.get_dashboard(dashboard_id)
        positions = self._build_positions(cards, title=dashboard.get("dashboard_title", "Dashboard"))

        # A chart in position_json is NOT enough on its own - Superset also
        # tracks a separate chart<->dashboard relation (found live: a chart
        # placed via this PUT alone rendered "There is no chart definition
        # associated with this component" because GET /api/v1/chart/:id's
        # own `dashboards` list was still empty). Native drag-and-drop saves
        # both at once; the API requires setting this side explicitly.
        for card in cards:
            self._put(f"/api/v1/chart/{card['card_id']}", {"dashboards": [dashboard_id]})

        return self._put(f"/api/v1/dashboard/{dashboard_id}", {
            "position_json": json.dumps(positions),
            # chart_configuration/global_chart_configuration mirror what
            # Superset's own dashboard builder writes for cross-filter
            # scoping - included so a chart placed via the API behaves the
            # same as one dragged in through the UI (found by saving a
            # dashboard from the UI and reading its json_metadata back).
            "json_metadata": json.dumps({
                "chart_configuration": {
                    str(c["card_id"]): {"id": c["card_id"], "crossFilters": {"scope": "global", "chartsInScope": []}}
                    for c in cards
                },
                "global_chart_configuration": {
                    "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
                    "chartsInScope": [c["card_id"] for c in cards],
                },
                "color_scheme": "",
                "label_colors": {},
                "shared_label_colors": {},
                "cross_filters_enabled": True,
            }),
        })

    def rename_card(self, card_id, name):
        return self._put(f"/api/v1/chart/{card_id}", {"slice_name": name})

    def get_card(self, card_id):
        return self._get(f"/api/v1/chart/{card_id}")

    def update_card_visualization_settings(self, card_id, settings_patch):
        """
        Closest Superset equivalent of Metabase's visualization_settings
        patch: merges into the chart's `params` JSON. Metabase's
        {"graph.colors": [hex]} is translated to Superset's per-series
        `color_scheme`/`label_colors` convention where recognizable,
        otherwise stored as-is under the same key for forward-compat.
        """
        chart = self.get_card(card_id)["result"]
        params = json.loads(chart.get("params") or "{}")

        if "graph.colors" in settings_patch:
            colors = settings_patch["graph.colors"]
            params["color_scheme"] = None
            params["label_colors"] = {"value": colors[0]} if colors else {}
        else:
            params.update(settings_patch)

        return self._put(f"/api/v1/chart/{card_id}", {"params": json.dumps(params)})

    def update_dashcard_layout(self, dashboard_id, layout_by_card_id):
        existing = self.get_dashboard_cards_summary(dashboard_id)
        for card in existing:
            patch = layout_by_card_id.get(card["card_id"], {})
            card.update(patch)
        return self._write_layout(dashboard_id, existing)

    def dashboard_url(self, dashboard_id):
        return f"{self.base_url}/superset/dashboard/{dashboard_id}/"

    def create_public_link(self, dashboard_id):
        """
        Superset has no one-call "public link" like Metabase. This project
        runs Superset with PUBLIC_ROLE_LIKE = "Gamma" (Docker/superset/
        superset_config.py) so any *published* dashboard is viewable
        unauthenticated - the same dev-grade trust trade-off Metabase's
        public link already makes elsewhere in this app. Publishing the
        dashboard is what actually exposes it; the URL itself just needs
        ?standalone=1 to drop Superset's own chrome for the iframe.
        """
        try:
            self._put(f"/api/v1/dashboard/{dashboard_id}", {"published": True})
        except SupersetError as ex:
            raise SupersetError(
                f"Could not publish the dashboard ({ex}). "
                "Check PUBLIC_ROLE_LIKE is set in Docker/superset/superset_config.py."
            )

        return f"{self.base_url}/superset/dashboard/{dashboard_id}/?standalone=1"

# AT Datalake — Project Overview

A self-hosted data lakehouse platform: ingest data from Postgres/MongoDB/Kafka,
process it in Spark, land it in an Apache Iceberg lakehouse backed by MinIO,
query it via Trino or plain Postgres, govern access with Apache Ranger,
visualize it in Metabase/Grafana, and generate ad-hoc dashboards from natural
language via a local LLM (Ollama). A Django REST backend and an Angular
frontend tie all of this together into one app.

This document is a from-scratch map of the whole system — read it top to
bottom if you're picking this project back up cold.

---

## 1. High-level architecture

```
                                Data Sources
                          (Postgres / MongoDB / Kafka)
                                     │
                                     ▼
                              Apache NiFi
                        (ingestion / flow orchestration)
                                     │
                                     ▼
                             Apache Spark
        (cleansing, validation, type conversion, dedup, enrichment)
                                     │
                                     ▼
                      Apache Iceberg REST Catalog
                    (table metadata, namespaces, schemas)
                                     │
                                     ▼
                                  MinIO
                (S3-compatible object store — the "warehouse")
                     ├── Iceberg metadata (JSON)
                     ├── Iceberg manifests (Avro)
                     └── Iceberg data files (Parquet)

Querying the lakehouse:
  Trino  ──(governed by)──▶  Apache Ranger  ──▶  Iceberg REST Catalog ──▶ MinIO
  Postgres (direct)          — used by the app's own SQL Editor for the
                               relational "datalake" DB, unrelated to Iceberg

Visualization: Metabase, Grafana  (point at Postgres / Trino)
AI: Ollama (local LLM) → "Playground" prompt-to-SQL-to-chart feature

Orchestration (sits outside the above data path, drives it on a schedule):
  Apache Airflow ──(hourly, via Django REST API)──▶ Ingestion pipelines
                    (calls POST /api/ingestion-pipelines/{id}/run/,
                     the same endpoint the "Data Ingestion" UI page calls,
                     which is what triggers NiFi at the top of this diagram)
```

The Angular frontend and Django backend are **not** containerized — they run
directly on the host (`ng serve` on :4200, Django `runserver` on :8000) and
talk to the dockerized infrastructure over `localhost` ports. Everything else
(20 services) runs in Docker via [`Docker/docker-compose.yml`](Docker/docker-compose.yml).

---

## 2. The Docker stack

All services join a single bridge network (`iceberg_net`) and are configured
with a **single set of credentials everywhere** for this dev environment:

> **Username: `shubham`   Password: `Shubham@123456`**

| Service | Image (official/upstream) | Host port(s) | Purpose |
|---|---|---|---|
| `postgres` | `postgres:16` | 5432 | The app's relational DB (`datalake`) — Django's own tables live in SQLite separately; this Postgres is for user-created data sources/destinations and is what the SQL Editor queries directly |
| `metabase` | `metabase/metabase:latest` | 3000 | BI dashboards, shares the `postgres` instance for its own metadata (via [init-postgres.sh](Docker/init-postgres.sh)) |
| `kafka` | `apache/kafka:3.9.0` | 9094 (external) | KRaft-mode broker (no Zookeeper), SASL/PLAIN auth |
| `kafka-ui` | `provectuslabs/kafka-ui:latest` | 8089 | Web UI for Kafka |
| `grafana` | `grafana/grafana:latest` | 3001 | Metrics dashboards |
| `influxdb` | `influxdb:2` | 8086 | Time-series store (org/bucket: `datalake`) |
| `nifi` | `apache/nifi:1.28.1` | 8443 (https) | Ingestion/flow orchestration |
| `spark-master` / `spark-worker` | `apache/spark:3.5.6` | 8080 / 8081, 7077 | Processing cluster (Java 11 — see Iceberg version note below) |
| `jupyter` | `jupyter/pyspark-notebook:latest` | 8888 | Notebook (token auth = the shared password) |
| `minio` + `mc` | `minio/minio`, `minio/mc` | 9000/9001 | S3-compatible warehouse; `mc` bootstraps the `warehouse` bucket |
| `iceberg-rest` + `iceberg-rest-init` | `apache/iceberg-rest-fixture:1.9.1` | 8181 | Iceberg REST catalog; `-init` is a one-shot `chown` fix for a volume-permission quirk in the image |
| `trino` | `trinodb/trino:470` | 8082 | SQL engine over the Iceberg catalog (catalog name: `iceberg`), governed by Ranger |
| `ranger-db` + `ranger` | `apache/ranger-db:2.8.0`, `apache/ranger:2.8.0` | 6080 | Access-control admin service for Trino |
| `ollama` + `ollama-init` | `ollama/ollama:0.33.2` | 11434 | Local LLM host; `-init` pulls the model once |
| `airflow-webserver` + `airflow-scheduler` (+ `airflow-db-init`, `airflow-init`) | `apache/airflow:2.10.4` | 8085 | Orchestrates the ingestion pipelines on an `@hourly` schedule by calling the Django API as a service account (`shubham@datalake.local`); `LocalExecutor`, own `airflow` Postgres DB. DAG: [Docker/airflow/dags/ingestion_pipelines_dag.py](Docker/airflow/dags/ingestion_pipelines_dag.py) |

Bring the whole stack up:
```bash
cd Docker
docker compose up -d
```

### Notable non-obvious things about this stack
- **`apache/ranger` doesn't take a mounted `install.properties` file** — its
  entrypoint overwrites that path with its own bundled template on every
  boot. Configuration instead goes through exactly three env vars
  (`POSTGRES_PASSWORD`, `RANGER_DB_USER`, `RANGER_DB_PASSWORD`), and its
  template hardcodes the Postgres superuser name to `postgres` — that's why
  `ranger-db` (unlike every other Postgres-backed service here) uses
  `POSTGRES_USER: postgres` instead of `shubham`.
- **Iceberg version is pinned to `1.6.1`** in the demo Spark job
  ([Docker/apps/iceberg_demo.py](Docker/apps/iceberg_demo.py)), not the
  latest (`1.11.0`). Newer Iceberg releases are compiled for Java 17;
  `apache/spark:3.5.6` ships Java 11 and throws
  `UnsupportedClassVersionError` on anything newer. Upgrading would mean
  switching the Spark base image.
- **`apache/iceberg-rest-fixture` runs as uid 1000**, so a fresh named
  volume (root-owned by default) breaks it — `iceberg-rest-init` chowns the
  volume once before the real service starts.
- **Trino's Ranger plugin is bundled in the stock image** for Trino ≥466 —
  no custom Trino build was needed, just config files under
  [Docker/trino/etc/](Docker/trino/etc/) (`access-control.properties`,
  `ranger-trino-security.xml`, `ranger-trino-audit.xml`,
  `ranger-policymgr-ssl.xml`).
- **`ollama-init` pulls `qwen2.5:1.5b`**, not `0.5b`. Both were tested live
  against real prompts; 0.5b too often produced broken/semantically wrong
  SQL (missing `GROUP BY`, wrong column, invented column names). `3b` was
  also tested but is impractically slow on this CPU-only host (timed out
  >60s for a single generation).

---

## 3. Data flow in detail: Source → Iceberg → MinIO

1. A **Data Source** (Postgres, MongoDB, or Kafka) is registered through the
   app's **Data Ingestion** page, which drives NiFi to move raw data.
2. **Spark** is the processing layer — see
   [Docker/apps/iceberg_demo.py](Docker/apps/iceberg_demo.py) for the
   canonical example: it reads a raw batch, then does real preprocessing
   (type casting, null/dedup filtering, an "enrichment" derived column) before
   writing anything downstream. This is deliberately where
   cleansing/validation/transformation logic belongs — not in NiFi.
3. The cleaned DataFrame is written via `df.writeTo("lakehouse.<namespace>.<table>").append()`
   against the **Iceberg REST Catalog** (`spark.sql.catalog.lakehouse.*`
   config, see the script's docstring for the exact `spark-submit` invocation).
4. The catalog persists table metadata and hands off actual data storage to
   **MinIO** — every write produces three artifact types: a `.parquet` data
   file, an `.avro` manifest, and a `.metadata.json` snapshot pointer.
5. From here, the data is queryable two ways:
   - **Trino** (`iceberg.<namespace>.<table>`) — governed by Ranger (see §5).
   - The backend's **Catalog API** (`/api/catalog/...`) reads the same REST
     catalog directly (via plain HTTP, no JVM dependency) to power the
     **Iceberg Catalog** frontend page — browse namespaces/tables, see schema
     and row/file/snapshot counts.

A worked example lives in `plant_ops.machine_readings` (created by the demo
script and by [fake-data-insert/seed_power_plant_data.py](fake-data-insert/seed_power_plant_data.py),
which seeds synthetic power-plant sensor readings into the plain Postgres
`datalake` DB — a separate, simpler dataset used to exercise the SQL Editor).

---

## 4. Backend (Django, `Backend/core/`)

Apps, each a thin Django app under `apps/`:

| App | Responsibility |
|---|---|
| `users` | JWT auth (login/logout), custom `User` model (email as username) |
| `data_sources` | CRUD for source connections (Postgres/Mongo/Kafka); `check-connection`/`list-buckets`/`list-assets` actions proxy to connector classes under `connectors/source/*` |
| `data_destination` | CRUD for destinations (MinIO is the only fully-wired type); exposes raw credentials via a `configuration`/`spark_config` action — **no auth on any of this**, flagged repeatedly, not yet fixed |
| `ingestion` | Pipeline CRUD + `/run/` action, which provisions a 3-processor NiFi flow (source → `ConvertRecord` → `PutS3Object`) via `services/job_builder.py` + `nifi_client.py` |
| `query` | SQL execution — `PostgresQueryRunner` (direct psycopg2 against a `DataSource`) and `TrinoQueryRunner` (executes as the **authenticated Django user's own identity**, so Ranger policies apply per-user); `QueryHistory` model backs the SQL Editor's "recent queries" |
| `catalog` | Read-only proxy to the Iceberg REST Catalog's own HTTP API — namespaces, tables, schema/stats |
| `playground` | Prompt-to-SQL: sends the user's NL prompt + a live schema summary to Ollama, extracts/validates the SQL (SELECT-only, keyword-blocklisted), executes it, and deterministically infers a chart type (`number`/`bar`/`line`/`table`) from the *actual* result shape — never trusted to the LLM |
| `ranger` | Pre-existing, empty scaffold from before this work — not registered in `INSTALLED_APPS`, unused |

Key settings (`core/settings.py`): `NIFI_URL`/`NIFI_USERNAME`/`NIFI_PASSWORD`,
`ICEBERG_REST_URL`, `OLLAMA_URL`/`OLLAMA_MODEL`, `TRINO_HOST`/`TRINO_PORT`/`TRINO_CATALOG`.

Run it:
```bash
cd Backend/core
python manage.py runserver 0.0.0.0:8000
```

### Known backend security gaps (carried forward from the original audit, not yet fixed)
- No `DEFAULT_PERMISSION_CLASSES` in `REST_FRAMEWORK` settings → every
  ViewSet without explicit `permission_classes` defaults to `AllowAny`. This
  means `data_sources`, `data_destination`, and `ingestion` are all
  **unauthenticated** — anyone can read/write data source credentials.
  The one exception built during this session: `/api/query/execute-trino/`
  explicitly requires `IsAuthenticated`, because Ranger governance is
  meaningless without knowing who's asking.
- `SECRET_KEY`, `DEBUG=True`, `CORS_ALLOW_ALL_ORIGINS=True` are all
  hardcoded/on in `settings.py` — fine for local dev, not for anything else.

---

## 5. Governance: Apache Ranger + Trino

- Trino's Ranger plugin (bundled in the official image) is configured to
  talk to the `ranger` admin service and enforce policies under a service
  named **`dev_trino`**.
- One real policy exists: user **`shubham`** has `select`/`show`/`use`/`execute`
  on the `iceberg` catalog (all schemas/tables/columns). No one else has any
  policy — Ranger denies by default.
- The backend's `TrinoQueryRunner` connects **as the Django-authenticated
  user's own identity** (derived from `email.split('@')[0]`), not a shared
  service account — so a request from a Django user with no matching Ranger
  policy gets a real `403 Access Denied` straight from Ranger, surfaced
  through `/api/query/execute-trino/`.
- A Django user `shubham@datalake.local` / `Shubham@123456` exists
  specifically so there's a real, working, authorized identity to test with
  end-to-end.

Ranger admin UI: `http://localhost:6080` (`admin` / `Shubham@123456`).

---

## 6. AI: Ollama + the "Playground" prompt-to-dashboard feature

- Model: `qwen2.5:1.5b`, served locally by the `ollama` container — no
  external API calls, no API key.
- Flow: user types a prompt on the **AI Playground** page → backend fetches
  a compact schema summary of the target Postgres data source → sends
  prompt+schema+few-shot examples to Ollama → extracts a single SQL
  statement (blocklisting anything but `SELECT`) → executes it → infers a
  chart type from the actual columns/rows returned → frontend renders it
  with Chart.js (bar/line) or a number card / table fallback.
- **Honest limitation**: even at 1.5b, the model sometimes still gets the
  semantics wrong (e.g. confusing "total readings" — a row count — with a
  nonexistent "reading value" column to sum). It reliably produces *valid*
  SQL far more often than *correct* SQL. This is a genuine small-model
  ceiling, not a bug — see the chat history for the side-by-side 0.5b vs
  1.5b vs 3b comparison that led to picking 1.5b.

---

## 7. Frontend (Angular 18 + PrimeNG 17, `Frontend/src/app/`)

| Component | Route | What it does |
|---|---|---|
| `login` | `/login` | Datalake-themed login page; JWT stored in localStorage |
| `main-layout` | (wraps everything) | Persistent top header (brand, search, notifications, profile/logout menu) + sidebar, present on **every** page |
| `sidebar` | — | Nav groups: Main, SQL, Data Engineering, **Tools** (external links to every infra UI — NiFi, Kafka UI, Spark, Trino, MinIO Console, Grafana, Metabase, Jupyter, Ranger, Airflow), AI/ML. Collapsible (10% width expanded / 60px icon rail collapsed) |
| `dashboard` | `/dashboard` (Home) | Real KPIs (data sources/destinations/pipeline counts, not fabricated), "New Notebook" opens Jupyter |
| `data-sources` / `data-destination` | `/data-sources`, `/data-destinations` | CRUD UIs for connections |
| `ingestion` | `/ingestion-pipelines` | "Add data" connector grid (Postgres/Mongo/Kafka cards) → 5-step wizard (Connection → Ingestion setup → Source → Destination → Schedule) → pipeline management |
| `query` | `/sql-editor`, `/queries` | SQL Editor: write/run SQL against Postgres, inline "Add Connection" dialog, recent-queries history |
| `iceberg-catalog` | `/iceberg-catalog` | Browse Iceberg namespaces/tables/schema/stats via the backend's Catalog API |
| `playground` | `/playground` | The prompt-to-dashboard feature described above |
| `module-view` | many placeholder routes | Generic stub component backing ~15 sidebar items that aren't real features yet (Learn, Workspace, Compute, Discover, Agents, AI Gateway, etc.) |

Environment config (`src/environments/environment*.ts`) holds every external
tool's URL (`metabaseUrl`, `jupyterUrl`, `nifiUrl`, `kafkaUiUrl`, `grafanaUrl`,
`minioConsoleUrl`, `trinoUrl`, `sparkUrl`, `rangerUrl`, `airflowUrl`) plus
`apiBaseUrl`.

Run it:
```bash
cd Frontend
npm install
ng serve   # http://localhost:4200
```

### Frontend fixes made along the way (worth knowing about)
- The JWT auth interceptor was **completely non-functional** until this
  session: wrong localStorage key, `JSON.parse` on a raw (non-JSON) token,
  and never actually registered (the real bootstrap file is `main.ts`, not
  the unused `app.config.ts`). Fixed — the interceptor now genuinely attaches
  `Authorization: Bearer <token>` to every request.
- The global stylesheet was missing PrimeNG's base structural CSS (only the
  theme CSS was imported), which silently broke `.p-inputgroup` flex layout
  app-wide. Fixed by importing `primeng/resources/primeng.min.css`.

---

## 8. Credentials quick-reference

| Where | Login |
|---|---|
| Everything infra-side (Postgres, MinIO, Kafka, NiFi, Grafana, InfluxDB, Ranger-DB) | `shubham` / `Shubham@123456` |
| Ranger admin UI | `admin` / `Shubham@123456` |
| Metabase | set up via its own web wizard on first visit (`shubham@datalake.local` used in earlier setup) |
| Jupyter | token = `Shubham@123456` |
| Django app user (Ranger-authorized) | `shubham@datalake.local` / `Shubham@123456` |
| Django app user (original) | `admin@admin.com` / *(unknown — never reset)* |

---

## 9. End-to-end verification commands (all actually run and passed at least once)

```bash
# Iceberg REST catalog healthy
curl -s http://localhost:8181/v1/config

# Trino can query the lakehouse (as the authorized user)
docker exec trino trino --user shubham --execute \
  "SELECT * FROM iceberg.plant_ops.machine_readings LIMIT 3"

# Same query as an unauthorized user -> Ranger denies it
docker exec trino trino --user intruder --execute \
  "SELECT * FROM iceberg.plant_ops.machine_readings LIMIT 3"

# Backend catalog API
curl -s http://localhost:8000/api/catalog/namespaces/
curl -s "http://localhost:8000/api/catalog/tables/?namespace=plant_ops"

# Full authenticated Trino-governed query through the Django API
TOKEN=$(curl -s -X POST http://localhost:8000/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"shubham@datalake.local","password":"Shubham@123456"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access'])")
curl -s -X POST http://localhost:8000/api/query/execute-trino/ \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"sql":"SELECT * FROM plant_ops.machine_readings LIMIT 3"}'
```

---

## 10. Where things live (file map for the parts built/changed this session)

```
Docker/
  docker-compose.yml          # the whole 20-service stack
  init-postgres.sh            # creates the "metabase" DB inside shared postgres
  trino/etc/                  # trino config incl. Ranger plugin XML/properties
  ranger/                     # (install.properties removed - see §2 note)
  airflow/dags/ingestion_pipelines_dag.py  # hourly ingestion-pipeline orchestration
  apps/iceberg_demo.py        # Spark -> Iceberg REST -> MinIO example job

Backend/core/
  core/settings.py            # all env-driven config for every integration
  apps/{users,data_sources,data_destination,ingestion,query,catalog,playground}/

Frontend/src/app/
  components/{login,main-layout,sidebar,dashboard,data-sources,
              data-destination,ingestion,query,iceberg-catalog,
              playground,module-view}/
  environments/environment*.ts

fake-data-insert/
  seed_power_plant_data.py    # sample Postgres data generator
```

---

## 11. Known limitations, summarized

- Most CRUD APIs (`data_sources`, `data_destination`, `ingestion`) are
  unauthenticated by default — a real deployment needs
  `DEFAULT_PERMISSION_CLASSES` set and those endpoints locked down.
- NiFi processor properties (topic name, table name, S3 bucket, credentials)
  aren't wired from the stored `DataSource`/`DataDestination` config into the
  actual NiFi processors yet — pipelines provision correctly but need manual
  NiFi UI configuration to actually move data.
- Ollama's SQL generation is best-effort; treat generated dashboards as a
  draft to verify, not ground truth.
- Trino's local Ranger policy-cache can't persist to disk (volume permission
  quirk) — cosmetic only, it just re-fetches from Ranger admin on restart.

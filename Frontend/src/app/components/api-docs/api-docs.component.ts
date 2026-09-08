import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

export interface ApiEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  path: string;
  title: string;
  description: string;
  auth: string;
  request: string;
  payload: string;
  response: string;
  sampleResult: string;
}

export interface ApiCategory {
  name: string;
  basePath: string;
  endpoints: ApiEndpoint[];
}

const API_BASE = 'http://localhost:8000/api';

const CATEGORIES: ApiCategory[] = [
  {
    name: 'Authentication',
    basePath: `${API_BASE}/users`,
    endpoints: [
      {
        method: 'POST',
        path: '/users/login/',
        title: 'Login',
        description: 'Authenticates a user by email/password and issues a JWT access + refresh token pair.',
        auth: 'None (AllowAny)',
        request: 'No query params. JSON body required.',
        payload: `{
  "email": "admin@admin.com",
  "password": "********"
}`,
        response: 'access/refresh JWT tokens plus the authenticated user\'s profile fields.',
        sampleResult: `{
  "message": "Login successful.",
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "first_name": "Admin",
    "last_name": "",
    "email": "admin@admin.com",
    "role": "admin"
  }
}`
      },
      {
        method: 'POST',
        path: '/users/logout/',
        title: 'Logout',
        description: 'Blacklists the given refresh token (if token blacklisting is enabled) and ends the session.',
        auth: 'JWT Bearer (IsAuthenticated)',
        request: 'Header: Authorization: Bearer <access_token>',
        payload: `{
  "refresh": "eyJhbGciOiJIUzI1NiIs..."
}`,
        response: 'Confirmation message. Always 200 unless an unexpected server error occurs.',
        sampleResult: `{
  "message": "Logged out successfully."
}`
      }
    ]
  },
  {
    name: 'Data Sources',
    basePath: `${API_BASE}/data-sources`,
    endpoints: [
      {
        method: 'GET',
        path: '/data-sources/',
        title: 'List data sources',
        description: 'Returns every configured DataSource (Postgres, Mongo, Kafka), newest first.',
        auth: 'None',
        request: 'No parameters.',
        payload: 'None (GET request).',
        response: 'Array of DataSource objects.',
        sampleResult: `[
  {
    "id": 14,
    "name": "Machines Postgres (NiFi)",
    "source_type": "postgres",
    "configuration": {
      "host": "postgres",
      "port": "5432",
      "database": "datalake",
      "username": "shubham",
      "password": "********"
    },
    "description": "",
    "is_active": true,
    "created_at": "2026-09-05T10:12:03Z",
    "updated_at": "2026-09-05T10:12:03Z"
  }
]`
      },
      {
        method: 'POST',
        path: '/data-sources/',
        title: 'Create data source',
        description: 'Registers a new source connection (postgres, mongo, or kafka) with its connection config.',
        auth: 'None',
        request: 'No query params. JSON body required.',
        payload: `{
  "name": "Orders Postgres",
  "source_type": "postgres",
  "description": "",
  "is_active": true,
  "configuration": {
    "host": "localhost",
    "port": "5432",
    "database": "datalake",
    "username": "shubham",
    "password": "********"
  }
}`,
        response: 'The created DataSource object, including its new id.',
        sampleResult: `{
  "id": 21,
  "name": "Orders Postgres",
  "source_type": "postgres",
  "configuration": { "host": "localhost", "port": "5432", "database": "datalake", "username": "shubham", "password": "********" },
  "description": "",
  "is_active": true,
  "created_at": "2026-09-08T09:41:12Z",
  "updated_at": "2026-09-08T09:41:12Z"
}`
      },
      {
        method: 'GET',
        path: '/data-sources/{id}/',
        title: 'Retrieve / Update / Delete data source',
        description: 'Standard detail route. GET fetches one source; PUT/PATCH update it; DELETE removes it.',
        auth: 'None',
        request: 'Path param: id (integer). PUT/PATCH take the same body shape as create.',
        payload: 'PUT/PATCH: same JSON shape as "Create data source". GET/DELETE: none.',
        response: 'The DataSource object (GET/PUT/PATCH) or 204 No Content (DELETE).',
        sampleResult: `{
  "id": 14,
  "name": "Machines Postgres (NiFi)",
  "source_type": "postgres",
  "configuration": { "host": "postgres", "port": "5432", "database": "datalake", "username": "shubham", "password": "********" },
  "description": "",
  "is_active": true,
  "created_at": "2026-09-05T10:12:03Z",
  "updated_at": "2026-09-05T10:12:03Z"
}`
      },
      {
        method: 'GET',
        path: '/data-sources/count/',
        title: 'Count data sources',
        description: 'Total number of configured data sources - used for the dashboard summary tiles.',
        auth: 'None',
        request: 'No parameters.',
        payload: 'None (GET request).',
        response: 'A single count field.',
        sampleResult: `{
  "count": 12
}`
      },
      {
        method: 'GET',
        path: '/data-sources/source-types/',
        title: 'List supported source types',
        description: 'The enum of source_type choices the "Add Data Source" form can offer.',
        auth: 'None',
        request: 'No parameters.',
        payload: 'None (GET request).',
        response: 'Array of {value, label} pairs.',
        sampleResult: `[
  { "value": "mongo", "label": "MongoDB" },
  { "value": "postgres", "label": "PostgreSQL" },
  { "value": "kafka", "label": "Kafka" }
]`
      },
      {
        method: 'GET',
        path: '/data-sources/{id}/check-connection/',
        title: 'Test a source connection',
        description: 'Attempts to actually connect using the stored credentials (used for MinIO/S3-style sources) and lists buckets on success.',
        auth: 'None',
        request: 'Path param: id (integer).',
        payload: 'None (GET request).',
        response: '{connected, buckets[]} on success, or {connected: false, error} with HTTP 400 on failure.',
        sampleResult: `{
  "connected": true,
  "buckets": ["staging", "warehouse"]
}`
      },
      {
        method: 'GET',
        path: '/data-sources/{id}/list-buckets/',
        title: 'List buckets',
        description: 'Lists buckets visible to an object-storage-type source.',
        auth: 'None',
        request: 'Path param: id (integer).',
        payload: 'None (GET request).',
        response: 'Raw bucket listing from the underlying connector (S3-style ListBuckets shape).',
        sampleResult: `{
  "Buckets": [
    { "Name": "staging" },
    { "Name": "warehouse" }
  ]
}`
      },
      {
        method: 'GET',
        path: '/data-sources/{id}/list-assets/',
        title: 'List assets in a bucket',
        description: 'Lists files inside a given bucket of an object-storage source.',
        auth: 'None',
        request: 'Path param: id (integer). Query param: bucket (string, required).',
        payload: 'None (GET request).',
        response: 'Array of file summaries.',
        sampleResult: `[
  {
    "name": "orders/2026-09-08/part-0001.json",
    "type": "json",
    "size": 4820,
    "last_modified": "2026-09-08T09:12:00Z"
  }
]`
      }
    ]
  },
  {
    name: 'Data Destinations',
    basePath: `${API_BASE}/data-destination`,
    endpoints: [
      {
        method: 'GET',
        path: '/data-destination/',
        title: 'List data destinations',
        description: 'Returns every configured DataDestination (currently MinIO-backed lakehouse targets), newest first.',
        auth: 'None',
        request: 'No parameters.',
        payload: 'None (GET request).',
        response: 'Array of DataDestination objects.',
        sampleResult: `[
  {
    "id": 4,
    "name": "MinIO (NiFi)",
    "destination_type": "minio",
    "configuration": {
      "endpoint": "http://minio:9000",
      "access_key": "shubham",
      "secret_key": "********",
      "bucket": "staging",
      "region": "us-east-1"
    },
    "description": "",
    "is_active": true,
    "created_at": "2026-09-05T10:14:00Z",
    "updated_at": "2026-09-05T10:14:00Z"
  }
]`
      },
      {
        method: 'POST',
        path: '/data-destination/',
        title: 'Create data destination',
        description: 'Registers a new destination. configuration is validated against destination_type-specific required fields (e.g. minio needs endpoint/access_key/secret_key).',
        auth: 'None',
        request: 'No query params. JSON body required.',
        payload: `{
  "name": "MinIO (NiFi)",
  "destination_type": "minio",
  "description": "",
  "is_active": true,
  "configuration": {
    "endpoint": "http://minio:9000",
    "access_key": "shubham",
    "secret_key": "********"
  }
}`,
        response: 'The created DataDestination object. 400 with a "configuration" error if required fields are missing.',
        sampleResult: `{
  "id": 5,
  "name": "MinIO (NiFi)",
  "destination_type": "minio",
  "configuration": { "endpoint": "http://minio:9000", "access_key": "shubham", "secret_key": "********" },
  "description": "",
  "is_active": true,
  "created_at": "2026-09-08T09:44:00Z",
  "updated_at": "2026-09-08T09:44:00Z"
}`
      },
      {
        method: 'GET',
        path: '/data-destination/{id}/',
        title: 'Retrieve / Update / Delete destination',
        description: 'Standard detail route. GET fetches one destination; PUT/PATCH update it; DELETE removes it.',
        auth: 'None',
        request: 'Path param: id (integer). PUT/PATCH take the same body shape as create.',
        payload: 'PUT/PATCH: same JSON shape as "Create data destination". GET/DELETE: none.',
        response: 'The DataDestination object (GET/PUT/PATCH) or 204 No Content (DELETE).',
        sampleResult: `{
  "id": 4,
  "name": "MinIO (NiFi)",
  "destination_type": "minio",
  "configuration": { "endpoint": "http://minio:9000", "access_key": "shubham", "secret_key": "********" },
  "description": "",
  "is_active": true,
  "created_at": "2026-09-05T10:14:00Z",
  "updated_at": "2026-09-05T10:14:00Z"
}`
      },
      {
        method: 'GET',
        path: '/data-destination/count/',
        title: 'Count data destinations',
        description: 'Total number of configured destinations - used for the dashboard summary tiles.',
        auth: 'None',
        request: 'No parameters.',
        payload: 'None (GET request).',
        response: 'A single count field.',
        sampleResult: `{
  "count": 5
}`
      },
      {
        method: 'GET',
        path: '/data-destination/destination-types/',
        title: 'List supported destination types',
        description: 'The enum of destination_type choices the "Add Destination" form can offer.',
        auth: 'None',
        request: 'No parameters.',
        payload: 'None (GET request).',
        response: 'Array of {value, label} pairs.',
        sampleResult: `[
  { "value": "minio", "label": "MinIO" }
]`
      },
      {
        method: 'GET',
        path: '/data-destination/{id}/configuration/',
        title: 'Get raw destination configuration',
        description: 'Returns the destination\'s stored configuration object as-is.',
        auth: 'None',
        request: 'Path param: id (integer).',
        payload: 'None (GET request).',
        response: 'Raw configuration JSON for that destination.',
        sampleResult: `{
  "endpoint": "http://minio:9000",
  "access_key": "shubham",
  "secret_key": "********",
  "bucket": "warehouse"
}`
      },
      {
        method: 'GET',
        path: '/data-destination/{id}/notebook/',
        title: 'Get Jupyter notebook URL',
        description: 'Returns the Jupyter Notebook URL associated with this destination, if configured.',
        auth: 'None',
        request: 'Path param: id (integer).',
        payload: 'None (GET request).',
        response: '{name, url}.',
        sampleResult: `{
  "name": "MinIO (NiFi)",
  "url": "http://localhost:8888/?token=Shubham@123456"
}`
      },
      {
        method: 'GET',
        path: '/data-destination/{id}/connection/',
        title: 'Get Spark/notebook connection info',
        description: 'Returns the engine/catalog/storage sub-sections of the configuration, as consumed by Spark or a notebook.',
        auth: 'None',
        request: 'Path param: id (integer).',
        payload: 'None (GET request).',
        response: '{engine, query_engine, catalog, storage}.',
        sampleResult: `{
  "engine": "spark",
  "query_engine": "trino",
  "catalog": { "type": "rest", "uri": "http://iceberg-rest:8181", "warehouse": "s3://warehouse/" },
  "storage": { "endpoint": "http://minio:9000", "access_key": "shubham", "secret_key": "********", "region": "us-east-1" }
}`
      },
      {
        method: 'GET',
        path: '/data-destination/{id}/spark_config/',
        title: 'Get ready-to-use Spark config',
        description: 'Flattens the destination\'s catalog/storage config into spark.sql.catalog.* properties a notebook can pass straight to a SparkSession.',
        auth: 'None',
        request: 'Path param: id (integer).',
        payload: 'None (GET request).',
        response: 'A flat map of Spark config keys to values.',
        sampleResult: `{
  "spark.sql.catalog.demo": "org.apache.iceberg.spark.SparkCatalog",
  "spark.sql.catalog.demo.type": "rest",
  "spark.sql.catalog.demo.uri": "http://iceberg-rest:8181",
  "spark.sql.catalog.demo.warehouse": "s3://warehouse/",
  "spark.sql.catalog.demo.io-impl": "org.apache.iceberg.aws.s3.S3FileIO",
  "spark.sql.catalog.demo.s3.endpoint": "http://minio:9000",
  "spark.sql.catalog.demo.s3.access-key-id": "shubham",
  "spark.sql.catalog.demo.s3.secret-access-key": "********",
  "spark.sql.catalog.demo.s3.region": "us-east-1"
}`
      }
    ]
  },
  {
    name: 'Ingestion Pipelines',
    basePath: `${API_BASE}/ingestion-pipelines`,
    endpoints: [
      {
        method: 'GET',
        path: '/ingestion-pipelines/',
        title: 'List ingestion pipelines',
        description: 'Returns every configured pipeline (source -> destination pairing) with its NiFi run status.',
        auth: 'None',
        request: 'No parameters.',
        payload: 'None (GET request).',
        response: 'Array of IngestionPipeline objects.',
        sampleResult: `[
  {
    "id": 7,
    "name": "Events to Lakehouse",
    "source": 17,
    "source_name": "Events Kafka (NiFi)",
    "destination": 4,
    "destination_name": "MinIO (NiFi)",
    "source_object": "orders-event",
    "sync_interval": "manual",
    "created_at": "2026-09-07T08:00:00Z",
    "updated_at": "2026-09-08T09:30:00Z"
  }
]`
      },
      {
        method: 'POST',
        path: '/ingestion-pipelines/',
        title: 'Create ingestion pipeline',
        description: 'Defines a new pipeline linking an existing source and destination. Does not start moving data - use the run action for that.',
        auth: 'None',
        request: 'No query params. JSON body required.',
        payload: `{
  "name": "Events to Lakehouse",
  "source": 17,
  "destination": 4,
  "source_object": "orders-event",
  "sync_interval": "manual"
}`,
        response: 'The created IngestionPipeline object.',
        sampleResult: `{
  "id": 7,
  "name": "Events to Lakehouse",
  "source": 17,
  "source_name": "Events Kafka (NiFi)",
  "destination": 4,
  "destination_name": "MinIO (NiFi)",
  "source_object": "orders-event",
  "sync_interval": "manual",
  "created_at": "2026-09-07T08:00:00Z",
  "updated_at": "2026-09-07T08:00:00Z"
}`
      },
      {
        method: 'GET',
        path: '/ingestion-pipelines/{id}/',
        title: 'Retrieve / Update / Delete pipeline',
        description: 'Standard detail route. GET fetches one pipeline; PUT/PATCH update it; DELETE removes it (and its NiFi process group ids stored on it - not the live NiFi resources themselves).',
        auth: 'None',
        request: 'Path param: id (integer). PUT/PATCH take the same body shape as create.',
        payload: 'PUT/PATCH: same JSON shape as "Create ingestion pipeline". GET/DELETE: none.',
        response: 'The IngestionPipeline object (GET/PUT/PATCH) or 204 No Content (DELETE).',
        sampleResult: `{
  "id": 7,
  "name": "Events to Lakehouse",
  "source": 17,
  "source_name": "Events Kafka (NiFi)",
  "destination": 4,
  "destination_name": "MinIO (NiFi)",
  "source_object": "orders-event",
  "sync_interval": "manual",
  "created_at": "2026-09-07T08:00:00Z",
  "updated_at": "2026-09-08T09:30:00Z"
}`
      },
      {
        method: 'GET',
        path: '/ingestion-pipelines/count/',
        title: 'Count ingestion pipelines',
        description: 'Total number of configured pipelines - used for the dashboard summary tiles.',
        auth: 'None',
        request: 'No parameters.',
        payload: 'None (GET request).',
        response: 'A single count field.',
        sampleResult: `{
  "count": 3
}`
      },
      {
        method: 'POST',
        path: '/ingestion-pipelines/{id}/run/',
        title: 'Run a pipeline',
        description: 'Builds (or reuses) the NiFi flow, starts it, waits for the batch to drain, stops it, then hands off the staged files to Spark to write them into Iceberg on MinIO as Parquet.',
        auth: 'None',
        request: 'Path param: id (integer). No body.',
        payload: 'None (POST with empty body).',
        response: '{success, message, result} where result includes the NiFi process-group/processor ids, the MinIO staging path, and (on success) the resulting Iceberg table name.',
        sampleResult: `{
  "success": true,
  "message": "Pipeline submitted successfully.",
  "result": {
    "process_group_id": "8f2c1e4a-...",
    "source_processor_id": "3a91c0d2-...",
    "destination_processor_id": "77b4e9f1-...",
    "staging_path": "s3a://staging/7/",
    "table": "lakehouse.ingested.orders_event"
  }
}`
      }
    ]
  },
  {
    name: 'Query & SQL Editor',
    basePath: `${API_BASE}/query`,
    endpoints: [
      {
        method: 'POST',
        path: '/query/execute/',
        title: 'Run SQL (SQL Editor)',
        description: 'Runs a statement against the lakehouse via Trino (catalog "iceberg", schema defaults to "ingested" so unqualified table names resolve to the ingested copy in MinIO). Governed by Apache Ranger for the caller\'s identity.',
        auth: 'JWT Bearer (IsAuthenticated)',
        request: 'Header: Authorization: Bearer <access_token>. No query params.',
        payload: `{
  "sql": "SELECT machine_name, pressure FROM power_plant_readings LIMIT 3"
}`,
        response: '{columns, rows, row_count, truncated, duration_ms} or {error} with 400/403.',
        sampleResult: `{
  "columns": ["machine_name", "pressure"],
  "rows": [
    ["Siemens Compressor-1", 13.63],
    ["Siemens Compressor-1", 12.24],
    ["Siemens Compressor-1", 12.67]
  ],
  "row_count": 3,
  "truncated": false,
  "duration_ms": 375
}`
      },
      {
        method: 'POST',
        path: '/query/execute-trino/',
        title: 'Run SQL (Trino Editor)',
        description: 'Runs a fully catalog/schema-qualified statement against Trino as the caller\'s own identity, so Ranger\'s per-user policies are enforced directly (no shared service account).',
        auth: 'JWT Bearer (IsAuthenticated)',
        request: 'Header: Authorization: Bearer <access_token>. No query params.',
        payload: `{
  "sql": "SELECT * FROM iceberg.ingested.orders_event LIMIT 5"
}`,
        response: '{columns, rows, row_count, truncated, duration_ms}. Returns 403 if Ranger denies the user, 400 on any other Trino error.',
        sampleResult: `{
  "columns": ["amount", "customer_name", "id", "order_date", "product"],
  "rows": [
    [389.45, "Rohan Mehta", "40b2beb1-...", "2026-09-07T12:28:01Z", "Noise-Cancelling Headphones"]
  ],
  "row_count": 1,
  "truncated": false,
  "duration_ms": 210
}`
      },
      {
        method: 'GET',
        path: '/query/trino/explorer/',
        title: 'Browse catalogs / schemas / tables / columns',
        description: 'Backs the Trino Editor\'s schema tree. Pass increasingly specific query params to drill down; every level is filtered by what Ranger allows the caller to see.',
        auth: 'JWT Bearer (IsAuthenticated)',
        request: 'Query params (all optional, each requires the previous one): catalog, schema, table.',
        payload: 'None (GET request).',
        response: 'One of {catalogs[]}, {schemas[]}, {tables[]}, or {columns[]} depending on which params were given.',
        sampleResult: `// GET /query/trino/explorer/?catalog=iceberg&schema=ingested
{
  "tables": ["orders_event", "power_plant_readings"]
}`
      },
      {
        method: 'GET',
        path: '/query/history/',
        title: 'List query history',
        description: 'Recent executed queries across both the SQL Editor and Trino Editor, newest first.',
        auth: 'None',
        request: 'Optional query param: source = "trino" | "postgres" to filter by execution path.',
        payload: 'None (GET request).',
        response: 'Array of QueryHistory objects.',
        sampleResult: `[
  {
    "id": 142,
    "data_source": null,
    "data_source_name": "Trino",
    "trino_user": "admin",
    "sql_text": "SELECT machine_name, pressure FROM power_plant_readings LIMIT 3",
    "status": "success",
    "row_count": 3,
    "duration_ms": 375,
    "error_message": null,
    "created_at": "2026-09-08T10:26:00Z"
  }
]`
      },
      {
        method: 'GET',
        path: '/query/history/{id}/',
        title: 'Retrieve one query history entry',
        description: 'Fetches a single past query execution by id.',
        auth: 'None',
        request: 'Path param: id (integer).',
        payload: 'None (GET request).',
        response: 'A single QueryHistory object.',
        sampleResult: `{
  "id": 142,
  "data_source": null,
  "data_source_name": "Trino",
  "trino_user": "admin",
  "sql_text": "SELECT machine_name, pressure FROM power_plant_readings LIMIT 3",
  "status": "success",
  "row_count": 3,
  "duration_ms": 375,
  "error_message": null,
  "created_at": "2026-09-08T10:26:00Z"
}`
      }
    ]
  },
  {
    name: 'Iceberg Catalog',
    basePath: `${API_BASE}/catalog`,
    endpoints: [
      {
        method: 'GET',
        path: '/catalog/namespaces/',
        title: 'List namespaces',
        description: 'Lists every namespace registered in the Iceberg REST Catalog (backed by MinIO).',
        auth: 'None',
        request: 'No parameters.',
        payload: 'None (GET request).',
        response: '{namespaces[]}, or {error} with 502 if the catalog is unreachable.',
        sampleResult: `{
  "namespaces": [["ingested"], ["plant_ops"]]
}`
      },
      {
        method: 'GET',
        path: '/catalog/tables/',
        title: 'List tables in a namespace',
        description: 'Lists every Iceberg table registered under a namespace.',
        auth: 'None',
        request: 'Query param: namespace (string, required).',
        payload: 'None (GET request).',
        response: '{namespace, tables[]}.',
        sampleResult: `{
  "namespace": "ingested",
  "tables": ["orders_event", "power_plant_readings"]
}`
      },
      {
        method: 'GET',
        path: '/catalog/tables/detail/',
        title: 'Get table detail',
        description: 'Fetches the Iceberg REST Catalog\'s full metadata for one table (schema, partitioning, snapshots, storage location in MinIO).',
        auth: 'None',
        request: 'Query params: namespace (string, required), table (string, required).',
        payload: 'None (GET request).',
        response: 'Raw Iceberg REST Catalog "load table" response.',
        sampleResult: `{
  "metadata-location": "s3://warehouse/ingested/orders_event/metadata/00003-....metadata.json",
  "metadata": {
    "schema": { "fields": [ { "name": "id", "type": "string" }, { "name": "amount", "type": "double" } ] },
    "current-snapshot-id": 5820476190234567000,
    "location": "s3://warehouse/ingested/orders_event"
  }
}`
      }
    ]
  },
  {
    name: 'AI Playground',
    basePath: `${API_BASE}/playground`,
    endpoints: [
      {
        method: 'POST',
        path: '/playground/generate/',
        title: 'Prompt to dashboard',
        description: 'Decomposes a plain-English prompt into a few chartable sub-questions using a local Ollama model, runs each against the selected Postgres data source, and creates a real Metabase Card + Dashboard from the results.',
        auth: 'None',
        request: 'No query params. JSON body required.',
        payload: `{
  "data_source": 2,
  "prompt": "Show average pressure per machine"
}`,
        response: '{prompt, dashboard_url, embed_url, widgets[]}. embed_url is null if Metabase "Public Sharing" isn\'t enabled yet.',
        sampleResult: `{
  "prompt": "Show average pressure per machine",
  "dashboard_url": "http://localhost:3000/dashboard/26",
  "embed_url": "http://localhost:3000/public/dashboard/fdeda8bf-f978-44f0-91e1-2f44e90864d9",
  "widgets": [
    {
      "title": "Average pressure per machine",
      "sql": "SELECT machine_name, AVG(pressure) AS average_pressure FROM power_plant_readings GROUP BY machine_name;",
      "row_count": 4,
      "duration_ms": 63,
      "chart_type": "bar",
      "error": null
    }
  ]
}`
      }
    ]
  }
];

@Component({
  selector: 'app-api-docs',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './api-docs.component.html',
  styleUrl: './api-docs.component.css'
})
export class ApiDocsComponent {

  categories = CATEGORIES;
  searchText = '';

  expanded = new Set<string>();

  key(categoryName: string, endpoint: ApiEndpoint): string {
    return `${categoryName}::${endpoint.method}::${endpoint.path}`;
  }

  isExpanded(categoryName: string, endpoint: ApiEndpoint): boolean {
    return this.expanded.has(this.key(categoryName, endpoint));
  }

  toggle(categoryName: string, endpoint: ApiEndpoint): void {
    const k = this.key(categoryName, endpoint);
    if (this.expanded.has(k)) {
      this.expanded.delete(k);
    } else {
      this.expanded.add(k);
    }
  }

  get filteredCategories(): ApiCategory[] {
    const term = this.searchText.trim().toLowerCase();

    if (!term) {
      return this.categories;
    }

    return this.categories
      .map(category => ({
        ...category,
        endpoints: category.endpoints.filter(endpoint =>
          endpoint.path.toLowerCase().includes(term) ||
          endpoint.title.toLowerCase().includes(term) ||
          endpoint.description.toLowerCase().includes(term) ||
          endpoint.method.toLowerCase().includes(term)
        )
      }))
      .filter(category => category.endpoints.length > 0);
  }

  scrollTo(categoryName: string): void {
    const el = document.getElementById(this.anchorId(categoryName));
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  anchorId(categoryName: string): string {
    return 'cat-' + categoryName.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  }
}

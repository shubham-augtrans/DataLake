"""
Orchestrates the ingestion pipelines that already exist in the Django app
(apps.ingestion.IngestionPipeline) - this DAG has no pipeline logic of its
own. It logs in to the same Django REST API the Angular frontend uses,
discovers every pipeline, and calls the same POST
/api/ingestion-pipelines/{id}/run/ endpoint the UI's "Run" button calls -
now on a schedule, with retries, and with a run history in the Airflow UI.

Django itself runs on the host (not in this docker-compose file - see the
commented-out "backend" service in Docker/docker-compose.yml), so it's
reached via host.docker.internal from inside the Airflow containers.
"""

from __future__ import annotations

import os

import pendulum
import requests
from airflow.decorators import dag, task
from airflow.exceptions import AirflowException

BACKEND_BASE_URL = os.environ.get("DATALAKE_BACKEND_URL", "http://host.docker.internal:8000/api")
SERVICE_EMAIL = os.environ.get("DATALAKE_SERVICE_EMAIL")
SERVICE_PASSWORD = os.environ.get("DATALAKE_SERVICE_PASSWORD")

REQUEST_TIMEOUT = 30
RUN_TIMEOUT = 900  # pipelines call out to NiFi + Spark; give them room


def _get_access_token() -> str:
    if not SERVICE_EMAIL or not SERVICE_PASSWORD:
        raise AirflowException(
            "DATALAKE_SERVICE_EMAIL / DATALAKE_SERVICE_PASSWORD are not set - "
            "set them on the airflow-* containers in docker-compose.yml to a "
            "real Django user's credentials."
        )

    response = requests.post(
        f"{BACKEND_BASE_URL}/users/login/",
        json={"email": SERVICE_EMAIL, "password": SERVICE_PASSWORD},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["access"]


default_args = {
    "owner": "datalake",
    "retries": 2,
    "retry_delay": pendulum.duration(minutes=5),
}


@dag(
    dag_id="datalake_ingestion_pipelines",
    description="Runs every ingestion pipeline defined in the Django app on a schedule.",
    schedule="@hourly",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["datalake", "ingestion"],
)
def datalake_ingestion_pipelines():

    @task
    def list_pipeline_ids() -> list[int]:
        token = _get_access_token()
        response = requests.get(
            f"{BACKEND_BASE_URL}/ingestion-pipelines/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        # DRF pagination wraps results in {"results": [...]}; an
        # unpaginated viewset just returns the list directly.
        pipelines = data.get("results", data) if isinstance(data, dict) else data
        return [pipeline["id"] for pipeline in pipelines]

    @task
    def run_pipeline(pipeline_id: int) -> dict:
        token = _get_access_token()
        response = requests.post(
            f"{BACKEND_BASE_URL}/ingestion-pipelines/{pipeline_id}/run/",
            headers={"Authorization": f"Bearer {token}"},
            json={"triggered_by": "airflow"},
            timeout=RUN_TIMEOUT,
        )

        try:
            result = response.json()
        except ValueError:
            response.raise_for_status()
            raise AirflowException(f"Pipeline {pipeline_id}: non-JSON response, HTTP {response.status_code}")

        if not result.get("success", False):
            raise AirflowException(f"Pipeline {pipeline_id} failed: {result.get('message')}")

        return result

    run_pipeline.expand(pipeline_id=list_pipeline_ids())


datalake_ingestion_pipelines()

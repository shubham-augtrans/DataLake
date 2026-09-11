import requests

from django.conf import settings


class NiFiClient:

    def __init__(self):

        self.base_url = settings.NIFI_URL.rstrip("/")

        self.session = requests.Session()

        # Development only.
        self.session.verify = False

        self._authenticate()

    def _authenticate(self):

        if (
            not settings.NIFI_USERNAME
            or not settings.NIFI_PASSWORD
        ):
            raise ValueError(
                "NIFI_USERNAME and NIFI_PASSWORD "
                "must be configured."
            )

        response = self.session.post(
            self._url("/access/token"),
            data={
                "username": settings.NIFI_USERNAME,
                "password": settings.NIFI_PASSWORD,
            },
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded",
            },
            timeout=30,
        )

        response.raise_for_status()

        token = response.text.strip()

        if not token:
            raise ValueError(
                "NiFi authentication returned "
                "an empty token."
            )

        self.session.headers.update({
            "Authorization": f"Bearer {token}",
        })

    def _url(self, path):

        return (
            f"{self.base_url}/"
            f"{path.lstrip('/')}"
        )
    def get_processor_type_details(self, processor_type):
        return self.get(
            f"/flow/processor-types/{processor_type}"
        )    
    def get_controller_service_types(self):
        return self.get(
            "/flow/controller-service-types"
        )
    def get_controller_service(
        self,
        controller_service_id,
    ):
        return self.get(
            f"/controller-services/"
            f"{controller_service_id}"
        )    
    def get(self, path, **kwargs):

        response = self.session.get(
            self._url(path),
            timeout=30,
            **kwargs,
        )

        response.raise_for_status()

        return response.json()

    def get_processor_types(self):

        return self.get(
            "/flow/processor-types"
        )    
    def get_processor(self, processor_id):
        return self.get(
            f"/processors/{processor_id}"
        )

    def post(self, path, data=None, **kwargs):
        response = self.session.post(
            self._url(path),
            json=data,
            timeout=30,
            **kwargs,
        )

        if not response.ok:
            raise Exception(
                f"NiFi API error {response.status_code}: "
                f"{response.text}\n"
                f"URL: {response.url}\n"
                f"Payload: {data}"
            )

        if response.content:
            return response.json()

        return None

    def put(self, path, data=None, **kwargs):

        response = self.session.put(
            self._url(path),
            json=data,
            timeout=30,
            **kwargs,
        )

        response.raise_for_status()

        return response.json()

    def delete(self, path, **kwargs):

        response = self.session.delete(
            self._url(path),
            timeout=30,
            **kwargs,
        )

        response.raise_for_status()

        if response.content:
            return response.json()

        return None

    # --------------------------------------------------
    # PROCESS GROUP
    # --------------------------------------------------

    def get_root_process_group(self):

        return self.get(
            "/flow/process-groups/root"
        )

    def get_root_process_group_id(self):

        result = self.get(
            "/flow/process-groups/root"
        )

        process_group_flow = result.get(
            "processGroupFlow"
        )

        if not process_group_flow:
            raise ValueError(
                "NiFi did not return processGroupFlow."
            )

        root_id = process_group_flow.get("id")

        if not root_id:
            raise ValueError(
                "NiFi root process group ID is empty."
            )

        return root_id   

    def create_process_group(
        self,
        parent_process_group_id,
        name,
        x=0,
        y=0,
    ):

        if not parent_process_group_id:
            raise ValueError(
                "parent_process_group_id is required."
            )

        payload = {
            "revision": {
                "version": 0,
            },
            "component": {
                "name": name,
                "position": {
                    "x": x,
                    "y": y,
                },
            },
        }

        return self.post(
            f"/process-groups/"
            f"{parent_process_group_id}/process-groups",
            payload,
        )

    # --------------------------------------------------
    # PROCESSOR
    # --------------------------------------------------

    def create_processor(
        self,
        process_group_id,
        processor_type,
        name,
        x=0,
        y=0,
    ):

        if not process_group_id:
            raise ValueError(
                "process_group_id is required."
            )

        payload = {
            "revision": {
                "version": 0,
            },
            "component": {
                "type": processor_type,
                "name": name,
                "position": {
                    "x": x,
                    "y": y,
                },
            },
        }

        return self.post(
            f"/process-groups/"
            f"{process_group_id}/processors",
            payload,
        )

    # --------------------------------------------------
    # UPDATE PROCESSOR
    # --------------------------------------------------

    def update_processor(
        self,
        processor_id,
        revision_version,
        properties,
    ):
        """
        NOTE: processor properties live under component.config.properties in
        NiFi's REST API (confirmed against a live 1.28.1 instance) - NOT
        component.properties directly, unlike controller services below.
        """

        payload = {
            "revision": {
                "version": revision_version,
            },
            "component": {
                "id": processor_id,
                "config": {
                    "properties": properties,
                },
            },
        }

        return self.put(
            f"/processors/{processor_id}",
            payload,
        )

    def set_processor_auto_terminated_relationships(
        self,
        processor_id,
        revision_version,
        relationships,
    ):
        payload = {
            "revision": {
                "version": revision_version,
            },
            "component": {
                "id": processor_id,
                "config": {
                    "autoTerminatedRelationships": relationships,
                },
            },
        }

        return self.put(
            f"/processors/{processor_id}",
            payload,
        )

    # --------------------------------------------------
    # RUN STATUS (start/stop processors, enable/disable services)
    # --------------------------------------------------

    def update_processor_run_status(self, processor_id, revision_version, state):
        """
        state: "RUNNING" or "STOPPED".
        """
        payload = {
            "revision": {"version": revision_version},
            "state": state,
        }

        return self.put(
            f"/processors/{processor_id}/run-status",
            payload,
        )

    def update_controller_service_run_status(self, service_id, revision_version, state):
        """
        state: "ENABLED" or "DISABLED". A processor referencing a controller
        service can't start until that service is ENABLED.
        """
        payload = {
            "revision": {"version": revision_version},
            "state": state,
        }

        return self.put(
            f"/controller-services/{service_id}/run-status",
            payload,
        )

    def get_process_group_status(self, process_group_id):
        return self.get(
            f"/flow/process-groups/{process_group_id}/status"
        )

    # --------------------------------------------------
    # CONNECTION
    # --------------------------------------------------

    def create_connection(
        self,
        process_group_id,
        source_id,
        destination_id,
        relationships=None,
    ):

        if not process_group_id:
            raise ValueError(
                "process_group_id is required."
            )

        if relationships is None:
            relationships = ["success"]

        payload = {
            "revision": {
                "version": 0,
            },
            "component": {
                "source": {
                    "id": source_id,
                    "groupId": process_group_id,
                    "type": "PROCESSOR",
                },
                "destination": {
                    "id": destination_id,
                    "groupId": process_group_id,
                    "type": "PROCESSOR",
                },
                "selectedRelationships": relationships,
            },
        }

        return self.post(
            f"/process-groups/"
            f"{process_group_id}/connections",
            payload,
        )

    def create_controller_service(
        self,
        process_group_id,
        service_type,
        name,
    ):
        payload = {
            "revision": {
                "version": 0,
            },
            "component": {
                "type": service_type,
                "name": name,
            },
        }

        return self.post(
            f"/process-groups/"
            f"{process_group_id}/controller-services",
            payload,
        )

    def get_controller_service(
        self,
        service_id,
    ):
        return self.get(
            f"/controller-services/{service_id}"
        )    


    def update_controller_service(
        self,
        service_id,
        revision_version,
        properties,
    ):
        payload = {
            "revision": {
                "version": revision_version,
            },
            "component": {
                "id": service_id,
                "properties": properties,
            },
        }

        return self.put(
            f"/controller-services/{service_id}",
            payload,
        )

    # --------------------------------------------------
    # DELETE / TEARDOWN
    # --------------------------------------------------

    def get_process_group_flow(self, process_group_id):
        return self.get(
            f"/flow/process-groups/{process_group_id}"
        )

    def get_process_group_controller_services(self, process_group_id):
        return self.get(
            f"/flow/process-groups/{process_group_id}/controller-services"
        )

    def delete_connection(self, connection_id, revision_version):
        return self.delete(
            f"/connections/{connection_id}",
            params={"version": revision_version},
        )

    def delete_processor(self, processor_id, revision_version):
        return self.delete(
            f"/processors/{processor_id}",
            params={"version": revision_version},
        )

    def delete_controller_service(self, service_id, revision_version):
        return self.delete(
            f"/controller-services/{service_id}",
            params={"version": revision_version},
        )

    def delete_process_group(self, process_group_id, revision_version):
        return self.delete(
            f"/process-groups/{process_group_id}",
            params={"version": revision_version},
        )

    def teardown_process_group(self, process_group_id):
        """
        Stops/disables and deletes everything inside a process group, then
        the group itself - the same manual sequence a stale test flow needs
        (stop processors -> delete connections -> delete processors ->
        disable+delete controller services -> delete process group).

        Used to clean up a pipeline's previous NiFi flow before rebuilding
        it, so re-running a pipeline reuses the slot instead of leaking a
        brand-new orphaned process group on every run. A missing group
        (already deleted, or never built) is treated as already torn down.
        """

        try:
            flow = self.get_process_group_flow(process_group_id)
        except requests.HTTPError as ex:
            if ex.response is not None and ex.response.status_code == 404:
                return
            raise

        contents = flow["processGroupFlow"]["flow"]

        for processor in contents.get("processors", []):
            component = processor["component"]
            if component.get("state") == "RUNNING":
                self.update_processor_run_status(
                    component["id"],
                    processor["revision"]["version"],
                    "STOPPED",
                )

        for connection in contents.get("connections", []):
            self.delete_connection(
                connection["component"]["id"],
                connection["revision"]["version"],
            )

        for processor in contents.get("processors", []):
            current = self.get_processor(processor["component"]["id"])
            self.delete_processor(
                current["component"]["id"],
                current["revision"]["version"],
            )

        services = self.get_process_group_controller_services(process_group_id)

        for service in services.get("controllerServices", []):
            component = service["component"]
            if component.get("state") == "ENABLED":
                self.update_controller_service_run_status(
                    component["id"],
                    service["revision"]["version"],
                    "DISABLED",
                )

        for service in services.get("controllerServices", []):
            current = self.get_controller_service(service["component"]["id"])
            self.delete_controller_service(
                current["component"]["id"],
                current["revision"]["version"],
            )

        group = self.get(f"/process-groups/{process_group_id}")
        self.delete_process_group(
            process_group_id,
            group["revision"]["version"],
        )
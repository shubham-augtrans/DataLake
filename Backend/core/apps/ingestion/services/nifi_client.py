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
            f"/nifi-api/processors/{processor_id}"
        )    

    # def update_controller_service(
    #     self,
    #     service_id,
    #     revision_version,
    #     properties,
    # ):
    #     payload = {
    #         "revision": {
    #             "version": revision_version,
    #         },
    #         "component": {
    #             "id": service_id,
    #             "properties": properties,
    #         },
    #     }

    #     return self.put(
    #         f"/nifi-api/controller-services/{service_id}",
    #         payload,
    #     )    
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

        payload = {
            "revision": {
                "version": revision_version,
            },
            "component": {
                "id": processor_id,
                "properties": properties,
            },
        }

        return self.put(
            f"/processors/{processor_id}",
            payload,
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
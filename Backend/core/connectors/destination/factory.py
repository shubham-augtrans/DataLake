from connectors.destination.postgres.connector import PostgresConnector
from connectors.destination.minio.connector import MinioConnector


class DestinationConnectorFactory:

    CONNECTORS = {
        "postgresql": PostgresConnector,
        "minio":MinioConnector,
    }

    @classmethod
    def get_connector(cls, destination):

        connector = cls.CONNECTORS.get(
            destination.destination_type
        )

        if connector is None:
            raise ValueError(
                f"Unsupported destination: {destination.destination_type}"
            )

        return connector(destination)
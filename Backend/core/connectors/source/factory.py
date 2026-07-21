from connectors.source.minio.connector import MinioConnector
from connectors.source.mongo.connector import MongoConnector

class SourceConnectorFactory:

    CONNECTORS = {
        "minio": MinioConnector,
        "mongo":MongoConnector,
    }

    @classmethod
    def get_connector(cls, datasource):

        connector = cls.CONNECTORS.get(datasource.source_type)

        if connector is None:
            raise ValueError(
                f"Unsupported source type: {datasource.source_type}"
            )

        return connector(datasource)
from connectors.source.factory import SourceConnectorFactory
from connectors.destination.factory import DestinationConnectorFactory

import io


class PipelineService:

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):

        source = SourceConnectorFactory.get_connector(
            self.pipeline.source
        )

        destination = DestinationConnectorFactory.get_connector(
            self.pipeline.destination
        )

        source_type = self.pipeline.source.source_type

        if source_type == "mongo":
            self._mongo_to_minio(source, destination)

        elif source_type == "minio":
            self._minio_to_destination(source, destination)

        else:
            raise Exception(
                f"Unsupported source type: {source_type}"
            )

    def _mongo_to_minio(self, mongo, minio):

        config = self.pipeline.source.configuration

        database = config["database"]

        collections = mongo.list_assets(database)

        for collection in collections:

            print(f"Ingesting collection: {collection}")

            df = mongo.read_asset(
                database_name=database,
                collection_name=collection,
            )

            if df.empty:
                print(f"Skipping empty collection {collection}")
                continue

            if "_id" in df.columns:
                df["_id"] = df["_id"].astype(str)

            minio.write_dataframe(
                dataframe=df,
                table_name=collection,
            )

            print(f"Uploaded {collection}")

    def _minio_to_destination(self, source, destination):

        bucket = self.pipeline.source.configuration["bucket"]

        assets = source.list_assets(bucket)

        for asset in assets:

            filename = asset["Key"]

            if not filename.endswith(".parquet"):
                continue

            print(f"Reading {filename}")

            df = source.read_asset(
                bucket,
                filename,
            )

            table_name = filename.replace(
                ".parquet",
                "",
            )

            destination.write_dataframe(
                df,
                table_name,
            )

            print(
                f"Loaded {filename} "
                f"into {table_name}"
            )
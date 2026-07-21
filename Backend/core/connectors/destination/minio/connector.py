import io

import boto3
import pandas as pd
from botocore.exceptions import ClientError

from connectors.destination.base import BaseDestinationConnector


class MinioConnector(BaseDestinationConnector):
    """
    MinIO Destination Connector
    """

    def __init__(self, destination):
        self.destination = destination

        config = destination.configuration

        if "storage" not in config:
            raise Exception("Missing 'storage' section in destination configuration.")

        self.storage = config["storage"]

        self.client = boto3.client(
            "s3",
            endpoint_url=self.storage["endpoint"],
            aws_access_key_id=self.storage["access_key"],
            aws_secret_access_key=self.storage["secret_key"],
            region_name=self.storage.get("region", "us-east-1"),
        )

    def check_connection(self):
        """
        Test MinIO connection.
        """
        try:
            return self.client.list_buckets()

        except ClientError as ex:
            raise Exception(f"Failed to connect to MinIO: {str(ex)}")

    def insert_rows(self, table_name, rows):
        """
        Convert rows into a DataFrame and upload as Parquet.
        """

        if not rows:
            return

        df = pd.DataFrame(rows)

        self.write_dataframe(df, table_name)

    def list_buckets(self):
        response = self.client.list_buckets()

        return [
            bucket["Name"]
            for bucket in response.get("Buckets", [])
        ]

    def create_bucket(self, bucket_name):
        try:
            self.client.head_bucket(Bucket=bucket_name)
        except ClientError:
            self.client.create_bucket(Bucket=bucket_name)

    def write_dataframe(
        self,
        dataframe,
        table_name,
    ):
        """
        Convert DataFrame to Parquet and upload to MinIO.
        """

        bucket = self.storage["bucket"]

        object_key = f"{table_name}.parquet"

        buffer = io.BytesIO()

        dataframe.to_parquet(
            buffer,
            engine="pyarrow",
            compression="snappy",
            index=False,
        )

        buffer.seek(0)

        self.client.upload_fileobj(
            buffer,
            bucket,
            object_key,
        )

    def upload_file(
        self,
        local_path,
        object_key,
    ):
        self.client.upload_file(
            local_path,
            self.storage["bucket"],
            object_key,
        )

    def download_file(
        self,
        object_key,
        local_path,
    ):
        self.client.download_file(
            self.storage["bucket"],
            object_key,
            local_path,
        )

    def list_assets(self):
        response = self.client.list_objects_v2(
            Bucket=self.storage["bucket"]
        )

        return response.get("Contents", [])

    def delete_asset(
        self,
        object_key,
    ):
        self.client.delete_object(
            Bucket=self.storage["bucket"],
            Key=object_key,
        )

    def close(self):
        pass
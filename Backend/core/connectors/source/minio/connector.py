import boto3
from botocore.exceptions import ClientError

from connectors.source.base import BaseConnector
import io
import pandas as pd

class MinioConnector(BaseConnector):
    """
    Connector for MinIO object storage.
    """

    def __init__(self, datasource):
        self.datasource = datasource

        config = datasource.configuration

        self.client = boto3.client(
            "s3",
            endpoint_url=config["endpoint"],
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
        )

    def check_connection(self):
        """
        Test the connection by listing buckets.
        """
        try:
            return self.client.list_buckets()

        except ClientError as ex:
            raise Exception(f"Failed to connect to MinIO: {str(ex)}")

    def list_buckets(self):
        """
        Return all buckets.
        """
        response = self.client.list_buckets()

        return [
            bucket["Name"]
            for bucket in response.get("Buckets", [])
        ]

    def list_assets(self, bucket_name):
        """
        List all objects inside a bucket.
        """
        response = self.client.list_objects_v2(
            Bucket=bucket_name
        )

        return response.get("Contents", [])

    def read_asset(self, bucket_name, object_key):
        obj = self.client.get_object(
            Bucket=bucket_name,
            Key=object_key
        )

        return pd.read_parquet(
            io.BytesIO(obj["Body"].read())
        )

    def download_asset(self, bucket_name, object_key, local_path):
        """
        Download an object to the local filesystem.
        """
        self.client.download_file(
            bucket_name,
            object_key,
            local_path,
        )

    def upload_asset(self, bucket_name, object_key, local_path):
        """
        Upload a local file to MinIO.
        """
        self.client.upload_file(
            local_path,
            bucket_name,
            object_key,
        )

    def delete_asset(self, bucket_name, object_key):
        """
        Delete an object from MinIO.
        """
        self.client.delete_object(
            Bucket=bucket_name,
            Key=object_key,
        )
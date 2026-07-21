import boto3


class MinioService:

    def __init__(self, datasource):

        config = datasource.configuration

        self.client = boto3.client(
            "s3",
            endpoint_url=config["endpoint"],
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
        )

    def list_buckets(self):
        return self.client.list_buckets()

    def list_files(self, bucket_name):
        return self.client.list_objects_v2(Bucket=bucket_name)

    def get_file(self, bucket, key):
        return self.client.get_object(
            Bucket=bucket,
            Key=key,
        )
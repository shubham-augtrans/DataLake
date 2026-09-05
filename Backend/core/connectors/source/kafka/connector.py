import pandas as pd
from kafka import KafkaAdminClient, KafkaConsumer
from kafka.errors import KafkaError

from connectors.source.base import BaseConnector


class KafkaConnector(BaseConnector):
    """
    Connector for Apache Kafka topics.
    """

    def __init__(self, datasource):
        self.datasource = datasource

        config = datasource.configuration

        self.bootstrap_servers = f"{config['host']}:{config.get('port', 9092)}"

        self.client_kwargs = {
            "bootstrap_servers": self.bootstrap_servers,
        }

        if config.get("username") and config.get("password"):
            self.client_kwargs.update({
                "security_protocol": config.get("security_protocol", "SASL_PLAINTEXT"),
                "sasl_mechanism": config.get("sasl_mechanism", "PLAIN"),
                "sasl_plain_username": config["username"],
                "sasl_plain_password": config["password"],
            })

    def check_connection(self):
        """
        Test the connection by listing topics via the admin client.
        """
        admin = None

        try:
            admin = KafkaAdminClient(**self.client_kwargs)

            return {
                "Buckets": [
                    {"Name": topic}
                    for topic in admin.list_topics()
                ]
            }

        except KafkaError as ex:
            raise Exception(f"Failed to connect to Kafka: {str(ex)}")

        finally:
            if admin is not None:
                admin.close()

    def list_buckets(self):
        """
        Return all topics (exposed generically as "buckets" by the UI).
        """
        admin = KafkaAdminClient(**self.client_kwargs)

        try:
            return admin.list_topics()

        finally:
            admin.close()

    def list_assets(self, topic):
        """
        List partitions for a topic.
        """
        consumer = KafkaConsumer(**self.client_kwargs)

        try:
            partitions = consumer.partitions_for_topic(topic) or set()

            return [
                {
                    "Key": f"{topic}-partition-{partition}",
                    "Size": 0,
                    "LastModified": None,
                }
                for partition in sorted(partitions)
            ]

        finally:
            consumer.close()

    def read_asset(self, topic, max_records=100):
        """
        Consume up to `max_records` messages from a topic into a DataFrame.
        """
        consumer = KafkaConsumer(
            topic,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            consumer_timeout_ms=5000,
            value_deserializer=lambda v: v.decode("utf-8", errors="replace"),
            **self.client_kwargs,
        )

        try:
            records = []

            for message in consumer:
                records.append({
                    "partition": message.partition,
                    "offset": message.offset,
                    "timestamp": message.timestamp,
                    "value": message.value,
                })

                if len(records) >= max_records:
                    break

            return pd.DataFrame(records)

        finally:
            consumer.close()

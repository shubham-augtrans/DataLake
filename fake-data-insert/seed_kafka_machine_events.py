"""
Publishes fake machine sensor events (machine name, temperature, pressure,
reading time) to a Kafka topic, for testing the Kafka -> MinIO ingestion
pipeline.

Uses the same SASL_PLAINTEXT/PLAIN credentials as the "Events Kafka" data
source already configured in the app, against the EXTERNAL listener the
Kafka container exposes on the host (see Docker/docker-compose.yml).

Usage:
    python seed_kafka_machine_events.py
    python seed_kafka_machine_events.py --topic machine-events --count 30 --interval 0.5

Requires: pip install kafka-python
"""

import argparse
import json
import random
import time
from datetime import datetime, timezone

from kafka import KafkaProducer

KAFKA_CONFIG = {
    "bootstrap_servers": ["localhost:9094"],
    "security_protocol": "SASL_PLAINTEXT",
    "sasl_mechanism": "PLAIN",
    "sasl_plain_username": "shubham",
    "sasl_plain_password": "Shubham@123456",
    "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
    "key_serializer": lambda k: k.encode("utf-8"),
}

MACHINES = [
    "Siemens Turbine-1",
    "Siemens Turbine-2",
    "Siemens Compressor-1",
    "Siemens Generator-1",
]

DEFAULT_TOPIC = "machine-events"
DEFAULT_COUNT = 20
DEFAULT_INTERVAL = 1.0


def generate_event():
    """
    One machine reading, shaped like the fields the Postgres seed script
    uses (machine_name, pressure, temperature, reading_time) so the same
    downstream table/schema expectations hold regardless of source type.
    """
    return {
        "machine_name": random.choice(MACHINES),
        "temperature": round(random.uniform(60.0, 120.0), 2),  # degrees C
        "pressure": round(random.uniform(8.0, 15.0), 2),       # bar
        "reading_time": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help=f"Kafka topic to publish to (default: {DEFAULT_TOPIC})")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help=f"Number of events to publish (default: {DEFAULT_COUNT})")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL, help=f"Seconds to sleep between events, 0 for a burst (default: {DEFAULT_INTERVAL})")
    args = parser.parse_args()

    producer = KafkaProducer(**KAFKA_CONFIG)

    try:
        for i in range(args.count):
            event = generate_event()

            producer.send(args.topic, key=event["machine_name"], value=event)
            producer.flush()

            print(f"[{i + 1}/{args.count}] -> {args.topic}: {event}")

            if args.interval > 0 and i < args.count - 1:
                time.sleep(args.interval)

    finally:
        producer.close()

    print(f"\nPublished {args.count} events to topic '{args.topic}'.")


if __name__ == "__main__":
    main()

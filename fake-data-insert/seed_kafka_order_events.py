"""
Publishes fake order events (order id, customer name, amount, order time) to
the "orders-event" Kafka topic, for testing the "Events to Lakehouse"
ingestion pipeline.

Same connection pattern as seed_kafka_machine_events.py - SASL_PLAINTEXT/PLAIN
against the Kafka broker's EXTERNAL listener on the host.

Usage:
    python seed_kafka_order_events.py
    python seed_kafka_order_events.py --topic orders-event --count 30 --interval 0.5

Requires: pip install kafka-python
"""

import argparse
import json
import random
import time
import uuid
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

CUSTOMERS = [
    "Aarav Sharma",
    "Priya Patel",
    "Rohan Mehta",
    "Ananya Gupta",
    "Vikram Singh",
    "Sneha Reddy",
]

PRODUCTS = [
    "Wireless Mouse",
    "Mechanical Keyboard",
    "USB-C Hub",
    "27in Monitor",
    "Laptop Stand",
    "Noise-Cancelling Headphones",
]

DEFAULT_TOPIC = "orders-event"
DEFAULT_COUNT = 20
DEFAULT_INTERVAL = 1.0


def generate_event():
    """
    One order event - shaped like the "orders(id, customer_name, amount,
    order_date)" example schema already used as a few-shot prompt in
    apps/playground/services.py, so it reads consistently across the app.
    """
    return {
        "id": str(uuid.uuid4()),
        "customer_name": random.choice(CUSTOMERS),
        "product": random.choice(PRODUCTS),
        "amount": round(random.uniform(15.0, 500.0), 2),
        "order_date": datetime.now(timezone.utc).isoformat(),
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

            producer.send(args.topic, key=event["id"], value=event)
            producer.flush()

            print(f"[{i + 1}/{args.count}] -> {args.topic}: {event}")

            if args.interval > 0 and i < args.count - 1:
                time.sleep(args.interval)

    finally:
        producer.close()

    print(f"\nPublished {args.count} events to topic '{args.topic}'.")


if __name__ == "__main__":
    main()

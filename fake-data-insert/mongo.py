import random
import string
import uuid
from datetime import datetime

from faker import Faker
from pymongo import MongoClient

fake = Faker()

# MongoDB Connection
client = MongoClient(
    "mongodb://mongoadmin:mongoadmin@localhost:27017/?authSource=admin"
)

db = client["datalake"]
collection = db["mixed_data"]

TARGET_SIZE = 1024 * 1024 * 1024  # 1 GB
BATCH_SIZE = 1000

inserted_bytes = 0
batch = []


def random_text(size):
    """Generate random text of approximately `size` bytes."""
    chars = string.ascii_letters + string.digits + " "
    return "".join(random.choices(chars, k=size))


while inserted_bytes < TARGET_SIZE:

    # Randomly choose document type
    if random.random() < 0.5:
        # -------------------------
        # Structured document
        # -------------------------
        doc = {
            "type": "structured",
            "record_id": str(uuid.uuid4()),
            "name": fake.name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "company": fake.company(),
            "job": fake.job(),
            "address": fake.address(),
            "city": fake.city(),
            "country": fake.country(),
            "salary": random.randint(30000, 250000),
            "age": random.randint(18, 70),
            "department": random.choice(
                ["HR", "IT", "Finance", "Sales", "Marketing"]
            ),
            "active": random.choice([True, False]),
            "created_at": datetime.utcnow(),
            "scores": [random.randint(0, 100) for _ in range(20)],
            "metadata": {
                "source": random.choice(["crm", "erp", "website"]),
                "version": random.randint(1, 10),
                "tags": fake.words(5),
            },
        }

    else:
        # -------------------------
        # Unstructured document
        # -------------------------
        text_size = random.randint(3000, 8000)

        doc = {
            "type": "unstructured",
            "doc_id": str(uuid.uuid4()),
            "title": fake.sentence(),
            "author": fake.name(),
            "created_at": datetime.utcnow(),
            "content": random_text(text_size),
            "summary": fake.paragraph(),
            "keywords": fake.words(10),
        }

    batch.append(doc)

    # Rough estimate of document size
    inserted_bytes += len(str(doc).encode("utf-8"))

    if len(batch) >= BATCH_SIZE:
        collection.insert_many(batch)
        print(
            f"Inserted ~{inserted_bytes / (1024 * 1024):.2f} MB",
            end="\r",
        )
        batch = []

# Insert remaining documents
if batch:
    collection.insert_many(batch)

print("\nDone!")
print(f"Approx inserted: {inserted_bytes / (1024 * 1024 * 1024):.2f} GB")
print(f"Documents in collection: {collection.count_documents({})}")
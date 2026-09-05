import random
import uuid
from datetime import datetime, timedelta

from faker import Faker
from pymongo import MongoClient

fake = Faker()

# -----------------------------
# MongoDB connection
# -----------------------------
client = MongoClient(
    "mongodb://mongoadmin:mongoadmin@localhost:27017/?authSource=admin"
)

db = client["datalake_structured"]
collection = db["structured_data"]

# -----------------------------
# Configuration
# -----------------------------
NUMBER_OF_RECORDS = 100

departments = [
    "IT",
    "Finance",
    "HR",
    "Sales",
    "Marketing",
    "Operations",
    "Engineering",
    "Customer Support",
]

job_titles = [
    "Software Engineer",
    "Data Analyst",
    "Product Manager",
    "Sales Executive",
    "HR Manager",
    "Financial Analyst",
    "Marketing Manager",
    "Operations Manager",
    "Customer Support Specialist",
    "DevOps Engineer",
]

countries = [
    "India",
    "USA",
    "UK",
    "Germany",
    "Canada",
    "Australia",
    "Singapore",
    "UAE",
]

cities = [
    "Mumbai",
    "Delhi",
    "Bangalore",
    "Hyderabad",
    "Pune",
    "Chennai",
    "New York",
    "London",
    "Toronto",
    "Dubai",
]

sources = [
    "CRM",
    "ERP",
    "Website",
    "Mobile App",
    "API",
]

# -----------------------------
# Generate documents
# -----------------------------
documents = []

for i in range(NUMBER_OF_RECORDS):

    department = random.choice(departments)
    country = random.choice(countries)
    city = random.choice(cities)

    age = random.randint(21, 60)

    # Salary correlated loosely with department/experience
    salary = random.randint(35000, 180000)

    created_at = datetime.utcnow() - timedelta(
        days=random.randint(0, 365)
    )

    document = {
        # Identification
        "type": "structured",
        "record_id": str(uuid.uuid4()),
        "employee_number": f"EMP-{i + 1:04d}",

        # Personal information
        "name": fake.name(),
        "email": fake.email(),
        "phone": fake.phone_number(),
        "age": age,

        # Work information
        "department": department,
        "job_title": random.choice(job_titles),
        "company": fake.company(),
        "salary": salary,

        # Location
        "country": country,
        "city": city,

        # Status
        "active": random.choice([True, True, True, False]),
        "employment_type": random.choice([
            "Full-time",
            "Part-time",
            "Contract",
        ]),

        # Performance
        "performance_score": random.randint(50, 100),
        "experience_years": random.randint(0, 20),

        # Dates
        "created_at": created_at,
        "last_login": created_at + timedelta(
            days=random.randint(1, 365)
        ),

        # Business metrics
        "sales_amount": round(random.uniform(1000, 100000), 2),
        "projects_completed": random.randint(0, 30),
        "customer_satisfaction": round(
            random.uniform(2.5, 5.0), 2
        ),

        # Data source
        "source": random.choice(sources),

        # Simple metadata
        "metadata": {
            "version": random.randint(1, 5),
            "region": random.choice([
                "North",
                "South",
                "East",
                "West",
            ]),
            "tags": random.sample(
                [
                    "new",
                    "experienced",
                    "remote",
                    "high_performer",
                    "manager",
                    "technical",
                    "sales",
                ],
                k=3,
            ),
        },
    }

    documents.append(document)


# -----------------------------
# Insert into MongoDB
# -----------------------------
result = collection.insert_many(documents)

print("===================================")
print("Insert completed")
print("===================================")
print(f"Inserted records : {len(result.inserted_ids)}")
print(f"Database         : {db.name}")
print(f"Collection       : {collection.name}")
print(
    f"Total documents  : {collection.count_documents({})}"
)

client.close()
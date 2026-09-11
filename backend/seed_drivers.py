import os
import random
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "agricentre")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is missing. Check backend/.env")

SEED_BATCH = "agricentre-drivers-v1"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

FIRST_NAMES = [
    "Aman", "Rohit", "Vivek", "Sandeep", "Nitin",
    "Rahul", "Manoj", "Pankaj", "Kunal", "Deepak",
    "Arjun", "Raj", "Vikas", "Mohit", "Ankit",
    "Ravi", "Sumit", "Ajay", "Sunil", "Prakash",
    "Harish", "Dinesh", "Rakesh", "Sachin", "Tarun",
    "Varun", "Gaurav", "Akash", "Lokesh", "Ashok",
    "Vijay", "Manish", "Yash", "Ramesh", "Karan",
    "Neeraj", "Suresh", "Naveen", "Abhishek", "Rajan",
    "Dev", "Amit", "Shubham", "Mayank", "Anurag",
    "Kapil", "Shivam", "Rajat", "Aditya", "Sanjay"
]

CITIES = [
    ("Delhi", "Delhi", 28.7041, 77.1025),
    ("Panipat", "Haryana", 29.3909, 76.9634),
    ("Hisar", "Haryana", 29.1492, 75.7217),
    ("Gurugram", "Haryana", 28.4595, 77.0266),
    ("Ludhiana", "Punjab", 30.9010, 75.8573),
    ("Amritsar", "Punjab", 31.6340, 74.8723),
    ("Jaipur", "Rajasthan", 26.9124, 75.7873),
    ("Kota", "Rajasthan", 25.2138, 75.8648),
    ("Ahmedabad", "Gujarat", 23.0225, 72.5714),
    ("Surat", "Gujarat", 21.1702, 72.8311),
    ("Lucknow", "Uttar Pradesh", 26.8467, 80.9462),
    ("Kanpur", "Uttar Pradesh", 26.4499, 80.3319),
    ("Agra", "Uttar Pradesh", 27.1767, 78.0081),
    ("Bhopal", "Madhya Pradesh", 23.2599, 77.4126),
    ("Indore", "Madhya Pradesh", 22.7196, 75.8577),
    ("Mumbai", "Maharashtra", 19.0760, 72.8777),
    ("Pune", "Maharashtra", 18.5204, 73.8567),
    ("Nagpur", "Maharashtra", 21.1458, 79.0882),
    ("Bengaluru", "Karnataka", 12.9716, 77.5946),
    ("Hyderabad", "Telangana", 17.3850, 78.4867),
    ("Chennai", "Tamil Nadu", 13.0827, 80.2707),
    ("Coimbatore", "Tamil Nadu", 11.0168, 76.9558),
    ("Kochi", "Kerala", 9.9312, 76.2673),
    ("Bhubaneswar", "Odisha", 20.2961, 85.8245),
    ("Patna", "Bihar", 25.5941, 85.1376),
    ("Ranchi", "Jharkhand", 23.3441, 85.3096),
    ("Kolkata", "West Bengal", 22.5726, 88.3639),
    ("Guwahati", "Assam", 26.1445, 91.7362),
    ("Dehradun", "Uttarakhand", 30.3165, 78.0322),
    ("Chandigarh", "Chandigarh", 30.7333, 76.7794)
]

VEHICLES = [
    ("Mini Truck", 1200),
    ("Pickup Truck", 1500),
    ("Medium Truck", 3000),
]

STATUSES = [
    "AVAILABLE", "AVAILABLE", "AVAILABLE",
    "AVAILABLE", "ON_DELIVERY"
]

STATE_CODES = {
    "Delhi": "DL", "Haryana": "HR", "Punjab": "PB",
    "Rajasthan": "RJ", "Gujarat": "GJ",
    "Uttar Pradesh": "UP", "Madhya Pradesh": "MP",
    "Maharashtra": "MH", "Karnataka": "KA",
    "Telangana": "TS", "Tamil Nadu": "TN",
    "Kerala": "KL", "Odisha": "OD", "Bihar": "BR",
    "Jharkhand": "JH", "West Bengal": "WB",
    "Assam": "AS", "Uttarakhand": "UK", "Chandigarh": "CH"
}

def generate_drivers():
    drivers = []

    for i in range(50):
        driver_id = f"DRV-{i + 1:03d}"
        name = FIRST_NAMES[i]
        city, state, lat, lon = CITIES[i % len(CITIES)]
        vehicle_type, capacity = random.choice(VEHICLES)
        state_code = STATE_CODES.get(state, "DL")

        vehicle_number = (
            f"{state_code}{random.randint(1, 99):02d}"
            f"{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}"
            f"{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}"
            f"{random.randint(1000, 9999)}"
        )

        drivers.append({
            "driver_id": driver_id,
            "name": name,
            "phone": f"9{random.randint(100000000, 999999999)}",
            "email": f"{name.lower()}.{i + 1}@demo.agricentre.in",
            "vehicle_type": vehicle_type,
            "vehicle_number": vehicle_number,
            "vehicle_capacity_kg": capacity,
            "rating": round(random.uniform(4.2, 5.0), 1),
            "status": random.choice(STATUSES),
            "city": city,
            "state": state,
            "location": {
                "type": "Point",
                "coordinates": [lon, lat]
            }
        })

    return drivers

DRIVERS = generate_drivers()

def seed_drivers():
    collection = db["drivers"]

    result = collection.delete_many({"seed_batch": SEED_BATCH})
    print(f"Removed old demo drivers: {result.deleted_count}")

    now = datetime.now(timezone.utc)

    documents = [
        {
            **driver,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "seed_batch": SEED_BATCH
        }
        for driver in DRIVERS
    ]

    if documents:
        collection.insert_many(documents)

    collection.create_index([("driver_id", ASCENDING)], unique=True)
    collection.create_index([("status", ASCENDING)])
    collection.create_index([("city", ASCENDING)])
    collection.create_index([("location", "2dsphere")])

    print(f"Inserted drivers: {len(documents)}")

if __name__ == "__main__":
    try:
        client.admin.command("ping")
        print("\nMongoDB connection: OK")
        print(f"Database: {DB_NAME}")

        seed_drivers()

        print("\n================================")
        print("DRIVER DATA CREATED SUCCESSFULLY")
        print("================================")

        for driver in DRIVERS:
            print(
                f"{driver['driver_id']} | {driver['name']} | "
                f"{driver['vehicle_type']} | "
                f"{driver['vehicle_number']} | {driver['city']}"
            )
    finally:
        client.close()

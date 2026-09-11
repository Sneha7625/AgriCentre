"""
AgriCentre demo database seeder.

Run from backend/:
    python seed_data.py

It uses the same MongoDB configuration as the existing Flask app and the
same Werkzeug password hashing used by auth_routes.py.

SAFE BY DEFAULT:
- Only documents marked with seed_batch="agricentre-demo-v1" are removed.
- Real users created through signup are not deleted.
- Re-running the script replaces only this demo batch.
"""

import os
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "agricentre")

if not MONGO_URI:
    raise RuntimeError(
        "MONGO_URI is missing. Check backend/.env before running seed_data.py."
    )

SEED_BATCH = "agricentre-demo-v1"
DEMO_PASSWORD = "Agri@123"

random.seed(26033)

NOW = datetime.now(timezone.utc).replace(microsecond=0)
START_DATE = NOW - timedelta(days=180)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


# ---------------------------------------------------------------------
# REFERENCE DATA
# ---------------------------------------------------------------------

LOCATIONS = [
    ("Ludhiana", "Punjab"),
    ("Amritsar", "Punjab"),
    ("Patiala", "Punjab"),
    ("Karnal", "Haryana"),
    ("Hisar", "Haryana"),
    ("Panipat", "Haryana"),
    ("Nashik", "Maharashtra"),
    ("Nagpur", "Maharashtra"),
    ("Pune", "Maharashtra"),
    ("Indore", "Madhya Pradesh"),
    ("Bhopal", "Madhya Pradesh"),
    ("Jaipur", "Rajasthan"),
    ("Kota", "Rajasthan"),
    ("Lucknow", "Uttar Pradesh"),
    ("Agra", "Uttar Pradesh"),
    ("Bengaluru", "Karnataka"),
    ("Mysuru", "Karnataka"),
    ("Ahmedabad", "Gujarat"),
    ("Surat", "Gujarat"),
    ("Delhi", "Delhi"),
]

CROPS = [
    ("Tomato", "Vegetables", "kg", 28, 55),
    ("Potato", "Vegetables", "kg", 18, 35),
    ("Onion", "Vegetables", "kg", 20, 42),
    ("Cabbage", "Vegetables", "kg", 16, 32),
    ("Cauliflower", "Vegetables", "kg", 24, 48),
    ("Carrot", "Vegetables", "kg", 28, 55),
    ("Spinach", "Leafy Vegetables", "kg", 18, 35),
    ("Green Chilli", "Vegetables", "kg", 45, 90),
    ("Okra", "Vegetables", "kg", 30, 65),
    ("Brinjal", "Vegetables", "kg", 22, 45),
    ("Wheat", "Grains", "kg", 24, 34),
    ("Rice", "Grains", "kg", 32, 58),
    ("Maize", "Grains", "kg", 18, 30),
    ("Mustard", "Oilseeds", "kg", 48, 72),
    ("Soybean", "Oilseeds", "kg", 38, 58),
    ("Cotton", "Cash Crops", "kg", 62, 95),
    ("Sugarcane", "Cash Crops", "kg", 3, 5),
    ("Mango", "Fruits", "kg", 55, 130),
    ("Apple", "Fruits", "kg", 85, 180),
    ("Banana", "Fruits", "dozen", 35, 70),
    ("Pomegranate", "Fruits", "kg", 90, 190),
    ("Guava", "Fruits", "kg", 40, 85),
]

FARMER_FIRST = [
    "Rajesh", "Harpreet", "Gurpreet", "Manpreet", "Sukhwinder",
    "Baldev", "Ramesh", "Mahesh", "Vijay", "Dinesh", "Anil",
    "Sunil", "Mohan", "Ravi", "Karan", "Amit", "Deepak", "Arjun",
    "Sanjay", "Prakash", "Devendra", "Naveen", "Rakesh", "Yogesh",
    "Pawan", "Mukesh", "Jitendra", "Suresh", "Naresh", "Vikas",
]

LAST_NAMES = [
    "Kumar", "Singh", "Sharma", "Verma", "Patel", "Yadav",
    "Mehta", "Gupta", "Joshi", "Chauhan", "Malhotra", "Gill",
]

WHOLESALE_NAMES = [
    "Sharma Agro Wholesale", "Kisan Bulk Foods", "GreenRoute Traders",
    "FreshHarvest Wholesale", "Bharat Grain Hub", "Punjab Produce Mart",
    "FarmLink Bulk Buyers", "National Agro Traders", "MandiDirect Foods",
    "HarvestGate Traders", "PrimeCrop Wholesale", "KrishiConnect Buyers",
    "RuralFresh Distributors", "AgroBridge Foods", "GreenBasket Bulk",
]

VENDOR_NAMES = [
    "FreshMart", "Daily Basket", "GreenLeaf Store", "Kisan Bazaar",
    "Farm2Home", "CityFresh Market", "Apna Grocery", "NatureCart",
    "Healthy Harvest Store", "LocalRoots Market", "Fresh Corner",
    "Urban Krishi", "GoodGrains Retail", "Green Basket", "FarmFresh Retail",
]

DRIVERS = [
    "Aman Verma", "Rohit Singh", "Vivek Kumar", "Sandeep Yadav",
    "Nitin Sharma", "Rahul Patel", "Manoj Gupta", "Pankaj Singh",
    "Kunal Mehta", "Deepak Chauhan",
]

VEHICLES = [
    "PB10AB4521", "HR26CD7812", "MH12EF3489", "DL01GH5623",
    "RJ14JK9012", "UP32LM6745", "KA01NP2387", "GJ05QR8194",
]


def pick_location():
    city, state = random.choice(LOCATIONS)
    return {
        "city": city,
        "state": state,
        "address": f"Agri collection point, {city}, {state}",
    }


def rand_date(start=START_DATE, end=NOW):
    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, max(1, seconds)))


def iso_day(dt):
    return dt.strftime("%Y-%m-%d")


def insert_many(collection_name, docs):
    if not docs:
        return
    db[collection_name].insert_many(docs, ordered=False)


def clean_demo_data():
    collections = [
        "users",
        "produce",
        "quality_checks",
        "offers",
        "orders",
        "payments",
        "deliveries",
        "market_data",
        "forecasts",
        "favorites",
        "notifications",
        "messages",
        "fpo_groups",
        "fpo_members",
        "disputes",
    ]

    for name in collections:
        result = db[name].delete_many({"seed_batch": SEED_BATCH})
        if result.deleted_count:
            print(f"  cleared {result.deleted_count:>4} demo docs from {name}")


# ---------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------

def create_users():
    users = []
    farmers = []
    wholesalers = []
    vendors = []

    # 40 farmers
    used_emails = set()

    for i in range(40):
        first = FARMER_FIRST[i % len(FARMER_FIRST)]
        last = random.choice(LAST_NAMES)
        city, state = random.choice(LOCATIONS)
        name = f"{first} {last}"

        email = f"farmer{i + 1:03d}@demo.agricentre.in"
        while email in used_emails:
            i += 1
            email = f"farmer{i + 1:03d}@demo.agricentre.in"
        used_emails.add(email)

        doc = {
            "name": name,
            "email": email,
            "password_hash": generate_password_hash(DEMO_PASSWORD),
            "phone": f"98{random.randint(10000000, 99999999)}",
            "address": f"Village {random.choice(['Khera', 'Nangal', 'Rampur', 'Kalan', 'Pur'])}, {city}, {state}",
            "role": "FARMER",
            "is_verified": random.random() < 0.78,
            "created_at": rand_date(NOW - timedelta(days=170), NOW - timedelta(days=20)),
            "seed_batch": SEED_BATCH,
            "demo_profile": {
                "farm_name": f"{last} Agro Farm",
                "farm_size_acres": round(random.uniform(2.5, 48), 1),
                "experience_years": random.randint(2, 28),
                "farming_type": random.choice(
                    ["Conventional", "Organic", "Mixed", "Natural Farming"]
                ),
            },
        }
        users.append(doc)
        farmers.append(doc)

    # 15 wholesalers
    for i, business in enumerate(WHOLESALE_NAMES):
        city, state = random.choice(LOCATIONS)
        doc = {
            "name": business,
            "email": f"wholesaler{i + 1:03d}@demo.agricentre.in",
            "password_hash": generate_password_hash(DEMO_PASSWORD),
            "phone": f"97{random.randint(10000000, 99999999)}",
            "address": f"Wholesale Market Road, {city}, {state}",
            "role": "WHOLESALER",
            "is_verified": random.random() < 0.9,
            "created_at": rand_date(NOW - timedelta(days=165), NOW - timedelta(days=15)),
            "seed_batch": SEED_BATCH,
            "demo_profile": {
                "business_name": business,
                "business_type": random.choice(
                    ["Bulk Buyer", "Food Distributor", "Agro Trader", "Institutional Buyer"]
                ),
                "service_area": random.choice(
                    ["Local", "State", "Multi-state", "North India"]
                ),
            },
        }
        users.append(doc)
        wholesalers.append(doc)

    # 15 vendors
    for i, business in enumerate(VENDOR_NAMES):
        city, state = random.choice(LOCATIONS)
        doc = {
            "name": business,
            "email": f"vendor{i + 1:03d}@demo.agricentre.in",
            "password_hash": generate_password_hash(DEMO_PASSWORD),
            "phone": f"96{random.randint(10000000, 99999999)}",
            "address": f"Main Market, {city}, {state}",
            "role": "VENDOR",
            "is_verified": random.random() < 0.86,
            "created_at": rand_date(NOW - timedelta(days=160), NOW - timedelta(days=10)),
            "seed_batch": SEED_BATCH,
            "demo_profile": {
                "business_name": business,
                "business_type": random.choice(
                    ["Retail Store", "Grocery", "Supermarket", "Local Retailer"]
                ),
                "store_area": random.choice(["Local", "City", "District"]),
            },
        }
        users.append(doc)
        vendors.append(doc)

    db["users"].insert_many(users)

    # Mongo assigns _id. Return actual documents.
    farmer_docs = list(
        db["users"].find({"seed_batch": SEED_BATCH, "role": "FARMER"})
    )
    wholesaler_docs = list(
        db["users"].find({"seed_batch": SEED_BATCH, "role": "WHOLESALER"})
    )
    vendor_docs = list(
        db["users"].find({"seed_batch": SEED_BATCH, "role": "VENDOR"})
    )

    return farmer_docs, wholesaler_docs, vendor_docs


# ---------------------------------------------------------------------
# PRODUCE + QUALITY
# ---------------------------------------------------------------------

def create_produce(farmers):
    listings = []
    quality = []

    statuses = ["ACTIVE"] * 65 + ["SOLD"] * 15 + ["PAUSED"] * 10 + ["DRAFT"] * 10

    for i in range(250):
        farmer = random.choice(farmers)
        crop, category, unit, low, high = random.choice(CROPS)

        loc = pick_location()
        # Keep some farmer/listing geography coherent.
        loc["city"] = farmer["address"].split(",")[-2].strip() if "," in farmer["address"] else loc["city"]

        price = round(random.uniform(low, high), 2)
        quantity = random.randint(50, 5000)
        listed_at = rand_date(START_DATE, NOW - timedelta(days=1))
        harvest_date = listed_at - timedelta(days=random.randint(0, 20))

        status = random.choice(statuses)

        listing_id = f"LIST-{i + 1:04d}"

        listing = {
            "listing_id": listing_id,
            "farmer_id": farmer["_id"],
            "farmer_name": farmer["name"],
            "produce_name": crop,
            "category": category,
            "description": f"Fresh {crop.lower()} sourced directly from the farm.",
            "quantity": quantity,
            "available_quantity": quantity,
            "unit": unit,
            "price": price,
            "minimum_order": random.choice([10, 25, 50, 100, 250]),
            "location": loc,
            "harvest_date": harvest_date,
            "availability_date": listed_at,
            "status": status,
            "image_url": f"assets/produce/{crop.lower().replace(' ', '-')}.jpg",
            "listed_at": listed_at,
            "seed_batch": SEED_BATCH,
        }
        listings.append(listing)

        # Most non-draft listings have a quality record.
        if status != "DRAFT" and random.random() < 0.92:
            grade = random.choices(["A", "B", "C"], weights=[55, 35, 10])[0]
            confidence = round(random.uniform(82, 99.2), 1)

            if grade == "A":
                result = "PASS"
                defects = random.choice(
                    [[], ["minor_surface_marks"], ["minor_size_variation"]]
                )
            elif grade == "B":
                result = random.choice(["PASS", "REVIEW"])
                defects = random.choice(
                    [["minor_surface_marks"], ["size_variation"], ["colour_variation"]]
                )
            else:
                result = random.choice(["REVIEW", "FAIL"])
                defects = random.choice(
                    [["visible_spots"], ["bruising"], ["surface_damage"], ["quality_variation"]]
                )

            quality.append(
                {
                    "quality_id": f"QC-{i + 1:04d}",
                    "listing_id": listing_id,
                    "farmer_id": farmer["_id"],
                    "produce_name": crop,
                    "grade": grade,
                    "confidence": confidence,
                    "result": result,
                    "detected_issues": defects,
                    "image_valid": True,
                    "model_version": "demo-quality-v1",
                    "admin_review_status": random.choice(
                        ["NOT_REVIEWED", "REVIEWED", "NOT_REQUIRED"]
                    ),
                    "checked_at": listed_at + timedelta(hours=random.randint(1, 48)),
                    "seed_batch": SEED_BATCH,
                }
            )

    insert_many("produce", listings)
    insert_many("quality_checks", quality)
    return listings, quality


# ---------------------------------------------------------------------
# OFFERS, ORDERS, PAYMENTS, DELIVERIES
# ---------------------------------------------------------------------

def create_transactions(listings, farmers, buyers):
    active_listings = [
        x for x in listings if x["status"] in {"ACTIVE", "SOLD", "PAUSED"}
    ]

    offers = []
    orders = []
    payments = []
    deliveries = []

    offer_statuses = ["PENDING", "ACCEPTED", "REJECTED", "COUNTERED", "EXPIRED"]
    order_statuses = ["PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"]

    for i in range(300):
        listing = random.choice(active_listings)
        buyer = random.choice(buyers)
        farmer = next(
            f for f in farmers if f["_id"] == listing["farmer_id"]
        )

        qty = min(
            random.choice([25, 50, 100, 200, 250, 500]),
            max(10, listing["quantity"])
        )
        listed_price = float(listing["price"])
        offered_price = round(
            max(listed_price * 0.75, listed_price + random.uniform(-4, 4)),
            2,
        )

        status = random.choice(offer_statuses)
        created = rand_date(START_DATE, NOW - timedelta(days=2))

        offers.append(
            {
                "offer_id": f"OFFER-{i + 1:04d}",
                "listing_id": listing["listing_id"],
                "farmer_id": farmer["_id"],
                "buyer_id": buyer["_id"],
                "buyer_role": buyer["role"],
                "produce_name": listing["produce_name"],
                "quantity": qty,
                "unit": listing["unit"],
                "listed_price": listed_price,
                "offered_price": offered_price,
                "status": status,
                "expires_at": created + timedelta(days=random.randint(1, 7)),
                "created_at": created,
                "negotiation": [
                    {
                        "actor": "BUYER",
                        "price": offered_price,
                        "timestamp": created,
                    }
                ],
                "seed_batch": SEED_BATCH,
            }
        )

    # 600 orders, with buyer/farmer/listing relationships.
    for i in range(600):
        listing = random.choice(active_listings)
        buyer = random.choice(buyers)
        farmer = next(f for f in farmers if f["_id"] == listing["farmer_id"])

        quantity = random.choice([20, 50, 75, 100, 150, 200, 250, 500])
        unit_price = round(
            listing["price"] * random.uniform(0.92, 1.08), 2
        )
        total = round(quantity * unit_price, 2)
        created = rand_date(START_DATE, NOW - timedelta(days=1))
        status = random.choice(order_statuses)

        order_id = f"ORD-{i + 1:05d}"

        order = {
            "order_id": order_id,
            "buyer_id": buyer["_id"],
            "buyer_name": buyer["name"],
            "buyer_role": buyer["role"],
            "farmer_id": farmer["_id"],
            "farmer_name": farmer["name"],
            "listing_id": listing["listing_id"],
            "produce_name": listing["produce_name"],
            "category": listing["category"],
            "quantity": quantity,
            "unit": listing["unit"],
            "unit_price": unit_price,
            "total_amount": total,
            "status": status,
            "created_at": created,
            "expected_delivery": created + timedelta(days=random.randint(1, 7)),
            "seed_batch": SEED_BATCH,
        }
        orders.append(order)

        # Most orders have a payment record.
        if status != "CANCELLED" or random.random() < 0.4:
            payment_status = (
                "PAID" if status in {"CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"}
                else random.choice(["PENDING", "PAID", "FAILED"])
            )
            platform_fee = round(total * 0.02, 2)
            logistics_fee = round(random.uniform(150, 1200), 2)
            farmer_payout = round(max(0, total - platform_fee - logistics_fee), 2)

            payments.append(
                {
                    "payment_id": f"PAY-{i + 1:05d}",
                    "order_id": order_id,
                    "buyer_id": buyer["_id"],
                    "farmer_id": farmer["_id"],
                    "amount": total,
                    "platform_fee": platform_fee,
                    "logistics_fee": logistics_fee,
                    "farmer_payout": farmer_payout,
                    "status": payment_status,
                    "payment_method": random.choice(
                        ["UPI", "BANK_TRANSFER", "CARD", "NET_BANKING"]
                    ),
                    "transaction_reference": f"AGRITXN{random.randint(10000000, 99999999)}",
                    "paid_at": (
                        created + timedelta(hours=random.randint(1, 72))
                        if payment_status == "PAID"
                        else None
                    ),
                    "seed_batch": SEED_BATCH,
                }
            )

        # Most non-cancelled orders have delivery.
        if status != "CANCELLED" and random.random() < 0.94:
            origin = listing["location"]
            destination = pick_location()

            delivery_status = {
                "PENDING": "SCHEDULED",
                "CONFIRMED": "SCHEDULED",
                "PROCESSING": random.choice(["SCHEDULED", "PICKED_UP"]),
                "SHIPPED": random.choice(["IN_TRANSIT", "OUT_FOR_DELIVERY"]),
                "DELIVERED": "DELIVERED",
            }.get(status, "SCHEDULED")

            distance = random.randint(15, 650)

            deliveries.append(
                {
                    "delivery_id": f"DEL-{i + 1:05d}",
                    "order_id": order_id,
                    "farmer_id": farmer["_id"],
                    "buyer_id": buyer["_id"],
                    "pickup_location": origin,
                    "destination": destination,
                    "driver_name": random.choice(DRIVERS),
                    "vehicle_number": random.choice(VEHICLES),
                    "distance_km": distance,
                    "status": delivery_status,
                    "estimated_cost": round(250 + distance * random.uniform(3.5, 6.5), 2),
                    "eta_hours": random.randint(4, 72),
                    "scheduled_at": created + timedelta(hours=random.randint(4, 48)),
                    "seed_batch": SEED_BATCH,
                }
            )

    insert_many("offers", offers)
    insert_many("orders", orders)
    insert_many("payments", payments)
    insert_many("deliveries", deliveries)

    return offers, orders, payments, deliveries


# ---------------------------------------------------------------------
# MARKET / DEMAND / FORECAST
# ---------------------------------------------------------------------

def create_market_data():
    market_docs = []
    forecasts = []

    markets = [
        "Delhi Azadpur", "Ludhiana Mandi", "Karnal Mandi",
        "Nashik Market", "Indore Mandi", "Jaipur Mandi",
        "Lucknow Market", "Bengaluru APMC", "Ahmedabad Market",
    ]

    # 2,500+ historical observations.
    for i in range(2600):
        crop, category, unit, low, high = random.choice(CROPS)
        market = random.choice(markets)
        dt = START_DATE + timedelta(days=random.randint(0, 179))

        seasonal = 1 + 0.12 * __import__("math").sin(dt.timetuple().tm_yday / 365 * 6.28)
        base_price = random.uniform(low, high)
        price = round(base_price * seasonal, 2)

        supply = random.randint(800, 18000)
        demand = random.randint(700, 20000)

        ratio = demand / max(supply, 1)
        if ratio >= 1.35:
            level = "VERY_HIGH"
        elif ratio >= 1.05:
            level = "HIGH"
        elif ratio >= 0.80:
            level = "MEDIUM"
        else:
            level = "LOW"

        market_docs.append(
            {
                "market_data_id": f"MD-{i + 1:05d}",
                "date": dt,
                "crop": crop,
                "category": category,
                "unit": unit,
                "market": market,
                "price": price,
                "demand_quantity": demand,
                "supply_quantity": supply,
                "demand_level": level,
                "seed_batch": SEED_BATCH,
            }
        )

    # 500 forecast points: crop + market + horizon.
    for i in range(500):
        crop, category, unit, low, high = random.choice(CROPS)
        market = random.choice(markets)
        historical_price = random.uniform(low, high)

        demand_score = random.uniform(0.45, 1.7)
        if demand_score >= 1.35:
            demand_level = "VERY_HIGH"
        elif demand_score >= 1.05:
            demand_level = "HIGH"
        elif demand_score >= 0.8:
            demand_level = "MEDIUM"
        else:
            demand_level = "LOW"

        forecasts.append(
            {
                "forecast_id": f"FC-{i + 1:05d}",
                "crop": crop,
                "category": category,
                "market": market,
                "forecast_date": NOW.date().isoformat(),
                "horizon_days": random.choice([7, 14, 30]),
                "predicted_demand_index": round(demand_score, 3),
                "predicted_demand_level": demand_level,
                "predicted_price": round(
                    historical_price * random.uniform(0.92, 1.14), 2
                ),
                "recommended_listing_low": round(
                    historical_price * random.uniform(0.95, 1.00), 2
                ),
                "recommended_listing_high": round(
                    historical_price * random.uniform(1.02, 1.15), 2
                ),
                "model_version": "demo-demand-v1",
                "confidence": round(random.uniform(72, 96), 1),
                "seed_batch": SEED_BATCH,
            }
        )

    insert_many("market_data", market_docs)
    insert_many("forecasts", forecasts)
    return market_docs, forecasts


# ---------------------------------------------------------------------
# USER-SUPPORT DATA
# ---------------------------------------------------------------------

def create_favorites(buyers, listings):
    docs = []
    used = set()

    for i in range(300):
        buyer = random.choice(buyers)
        listing = random.choice(listings)
        key = (str(buyer["_id"]), listing["listing_id"])

        if key in used:
            continue
        used.add(key)

        docs.append(
            {
                "favorite_id": f"FAV-{len(docs) + 1:04d}",
                "user_id": buyer["_id"],
                "listing_id": listing["listing_id"],
                "created_at": rand_date(START_DATE, NOW),
                "seed_batch": SEED_BATCH,
            }
        )

    insert_many("favorites", docs)


def create_notifications(users):
    templates = [
        ("New offer received", "An offer was received on your produce listing.", "OFFER"),
        ("Order confirmed", "Your order has been confirmed.", "ORDER"),
        ("Payment update", "A payment status has changed.", "PAYMENT"),
        ("Quality check complete", "Your produce quality check has been completed.", "QUALITY"),
        ("Delivery update", "Your shipment status has been updated.", "DELIVERY"),
        ("Verification update", "Your account verification status has been updated.", "VERIFICATION"),
        ("Demand alert", "Demand for one of your tracked crops is increasing.", "MARKET"),
    ]

    docs = []

    for i in range(400):
        user = random.choice(users)
        title, message, ntype = random.choice(templates)

        docs.append(
            {
                "notification_id": f"NOT-{i + 1:05d}",
                "user_id": user["_id"],
                "title": title,
                "message": message,
                "type": ntype,
                "is_read": random.random() < 0.55,
                "created_at": rand_date(START_DATE, NOW),
                "seed_batch": SEED_BATCH,
            }
        )

    insert_many("notifications", docs)


def create_messages(users, orders, offers):
    docs = []

    for i in range(250):
        buyer = random.choice([u for u in users if u["role"] != "FARMER"])
        farmer = random.choice([u for u in users if u["role"] == "FARMER"])

        order = random.choice(orders) if orders else None
        offer = random.choice(offers) if offers else None

        messages = [
            "Can you confirm the available quantity?",
            "Is the quoted price negotiable for bulk quantity?",
            "Please share the expected pickup date.",
            "The quality looks good. We would like to proceed.",
            "Can we arrange delivery to the wholesale market?",
            "Please confirm the invoice details.",
        ]

        docs.append(
            {
                "message_id": f"MSG-{i + 1:05d}",
                "conversation_id": f"CONV-{random.randint(1, 100):04d}",
                "sender_id": random.choice([buyer["_id"], farmer["_id"]]),
                "receiver_id": random.choice([buyer["_id"], farmer["_id"]]),
                "order_id": order["order_id"] if order else None,
                "offer_id": offer["offer_id"] if offer else None,
                "message": random.choice(messages),
                "attachment": None,
                "is_read": random.random() < 0.7,
                "timestamp": rand_date(START_DATE, NOW),
                "seed_batch": SEED_BATCH,
            }
        )

    insert_many("messages", docs)


# ---------------------------------------------------------------------
# FPO / DISPUTES
# ---------------------------------------------------------------------

def create_fpos(farmers):
    groups = []
    members = []

    fpo_names = [
        "Punjab Green Farmers FPO",
        "Malwa Fresh Producers FPO",
        "Haryana Harvest Collective",
        "Nashik Fruit Growers FPO",
        "Madhya Pradesh Kisan FPO",
        "Rajasthan Agri Producers FPO",
        "UP Fresh Crop Collective",
        "Karnataka Green Produce FPO",
    ]

    for i, name in enumerate(fpo_names):
        loc = pick_location()
        fpo_id = f"FPO-{i + 1:03d}"

        groups.append(
            {
                "fpo_id": fpo_id,
                "name": name,
                "location": loc,
                "status": "ACTIVE",
                "member_count": random.randint(8, 35),
                "created_at": rand_date(NOW - timedelta(days=150), NOW - timedelta(days=30)),
                "seed_batch": SEED_BATCH,
            }
        )

        selected = random.sample(farmers, min(random.randint(8, 15), len(farmers)))

        for farmer in selected:
            members.append(
                {
                    "fpo_id": fpo_id,
                    "farmer_id": farmer["_id"],
                    "joined_at": rand_date(NOW - timedelta(days=140), NOW),
                    "status": "ACTIVE",
                    "seed_batch": SEED_BATCH,
                }
            )

    insert_many("fpo_groups", groups)
    insert_many("fpo_members", members)


def create_disputes(users, orders):
    docs = []
    statuses = ["OPEN", "UNDER_REVIEW", "RESOLVED", "CLOSED"]

    for i in range(30):
        order = random.choice(orders)
        buyer = next(
            u for u in users if u["_id"] == order["buyer_id"]
        )
        farmer = next(
            u for u in users if u["_id"] == order["farmer_id"]
        )

        docs.append(
            {
                "dispute_id": f"DSP-{i + 1:04d}",
                "order_id": order["order_id"],
                "opened_by": random.choice([buyer["_id"], farmer["_id"]]),
                "buyer_id": buyer["_id"],
                "farmer_id": farmer["_id"],
                "reason": random.choice(
                    [
                        "Quantity mismatch",
                        "Quality concern",
                        "Delivery delay",
                        "Payment issue",
                        "Damaged produce",
                    ]
                ),
                "description": "Demo operational dispute for testing the resolution workflow.",
                "status": random.choice(statuses),
                "created_at": rand_date(START_DATE, NOW),
                "seed_batch": SEED_BATCH,
            }
        )

    insert_many("disputes", docs)


# ---------------------------------------------------------------------
# INDEXES
# ---------------------------------------------------------------------

def create_indexes():
    db["users"].create_index([("email", ASCENDING)], unique=True)
    db["produce"].create_index([("farmer_id", ASCENDING)])
    db["produce"].create_index([("produce_name", ASCENDING)])
    db["orders"].create_index([("buyer_id", ASCENDING)])
    db["orders"].create_index([("farmer_id", ASCENDING)])
    db["orders"].create_index([("status", ASCENDING)])
    db["offers"].create_index([("farmer_id", ASCENDING)])
    db["offers"].create_index([("buyer_id", ASCENDING)])
    db["deliveries"].create_index([("order_id", ASCENDING)])
    db["market_data"].create_index([("crop", ASCENDING), ("date", ASCENDING)])
    db["notifications"].create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    print("\n=== AgriCentre Demo Dataset Seeder ===")
    print(f"Database: {DB_NAME}")
    print(f"Seed batch: {SEED_BATCH}\n")

    # Confirm connection before making changes.
    client.admin.command("ping")
    print("MongoDB connection: OK")

    print("\n1) Clearing previous AgriCentre demo batch...")
    clean_demo_data()

    print("\n2) Creating users...")
    farmers, wholesalers, vendors = create_users()
    buyers = wholesalers + vendors
    all_users = farmers + buyers
    print(f"   Farmers:     {len(farmers)}")
    print(f"   Wholesalers: {len(wholesalers)}")
    print(f"   Vendors:     {len(vendors)}")

    print("\n3) Creating produce + quality...")
    listings, quality = create_produce(farmers)
    print(f"   Listings:    {len(listings)}")
    print(f"   Quality:     {len(quality)}")

    print("\n4) Creating offers + orders + payments + deliveries...")
    offers, orders, payments, deliveries = create_transactions(
        listings, farmers, buyers
    )
    print(f"   Offers:      {len(offers)}")
    print(f"   Orders:      {len(orders)}")
    print(f"   Payments:    {len(payments)}")
    print(f"   Deliveries:  {len(deliveries)}")

    print("\n5) Creating market/demand + forecast data...")
    market, forecasts = create_market_data()
    print(f"   Market rows: {len(market)}")
    print(f"   Forecasts:   {len(forecasts)}")

    print("\n6) Creating favorites, notifications and messages...")
    create_favorites(buyers, listings)
    create_notifications(all_users)
    create_messages(all_users, orders, offers)

    print("\n7) Creating FPO and dispute data...")
    create_fpos(farmers)
    create_disputes(all_users, orders)

    print("\n8) Creating indexes...")
    create_indexes()

    print("\n=== DONE ===")
    print(f"Database '{DB_NAME}' now contains the AgriCentre demo dataset.")
    print(f"Demo password for seeded accounts: {DEMO_PASSWORD}")
    print("\nExample accounts:")
    print("  farmer001@demo.agricentre.in")
    print("  wholesaler001@demo.agricentre.in")
    print("  vendor001@demo.agricentre.in")
    print(f"  password: {DEMO_PASSWORD}\n")

    client.close()


if __name__ == "__main__":
    main()

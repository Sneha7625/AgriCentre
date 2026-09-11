"""
AgriCentre - Payment Collection Rebuilder

Rebuilds ONLY the payments collection using the
existing orders + deliveries data.

DO NOT run seed_data.py before this.
"""

import os
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pymongo import MongoClient


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "agricentre")

SEED_BATCH = "agricentre-demo-v1"


if not MONGO_URI:
    raise RuntimeError(
        "MONGO_URI is missing. Check backend/.env"
    )


# ============================================================
# DATABASE
# ============================================================

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

orders_col = db["orders"]
deliveries_col = db["deliveries"]
payments_col = db["payments"]


# ============================================================
# HELPERS
# ============================================================

def money(value):
    return round(float(value or 0), 2)


def get_delivery(order_id):
    """
    Get delivery information for an order.

    Some orders do not have a delivery record yet.
    """

    return deliveries_col.find_one(
        {
            "order_id": order_id,
            "seed_batch": SEED_BATCH
        }
    )


def get_payment_state(order, delivery):
    """
    Determine the initial demo payment state.

    Business rule:

    1. Buyer pays 50% advance.
    2. Remaining 50% is locked until delivery.
    3. Once delivered, final 50% becomes payable.
    4. Some seeded delivered orders are marked fully paid
       so the dashboard demonstrates all states.
    """

    order_status = order.get("status", "PENDING")

    delivery_status = (
        delivery.get("status")
        if delivery
        else None
    )

    # --------------------------------------------------------
    # CANCELLED
    # --------------------------------------------------------

    if order_status == "CANCELLED":

        return {
            "advance": "CANCELLED",
            "final": "LOCKED",
            "overall": "CANCELLED"
        }

    # --------------------------------------------------------
    # DELIVERED
    # --------------------------------------------------------

    if (
        order_status == "DELIVERED"
        or delivery_status == "DELIVERED"
    ):

        # About half of delivered demo orders will still
        # need their final 50%.
        if random.random() < 0.55:

            return {
                "advance": "PAID",
                "final": "PENDING",
                "overall": "FINAL_PAYMENT_DUE"
            }

        else:

            return {
                "advance": "PAID",
                "final": "PAID",
                "overall": "COMPLETELY_PAID"
            }

    # --------------------------------------------------------
    # IN TRANSIT / OUT FOR DELIVERY / PICKED UP
    # --------------------------------------------------------

    if delivery_status in {
        "IN_TRANSIT",
        "OUT_FOR_DELIVERY",
        "PICKED_UP"
    }:

        return {
            "advance": "PAID",
            "final": "LOCKED",
            "overall": "ADVANCE_PAID"
        }

    # --------------------------------------------------------
    # SHIPPED
    # --------------------------------------------------------

    if order_status == "SHIPPED":

        return {
            "advance": "PAID",
            "final": "LOCKED",
            "overall": "ADVANCE_PAID"
        }

    # --------------------------------------------------------
    # CONFIRMED / PROCESSING
    # --------------------------------------------------------

    if order_status in {
        "CONFIRMED",
        "PROCESSING"
    }:

        return {
            "advance": "PAID",
            "final": "LOCKED",
            "overall": "ADVANCE_PAID"
        }

    # --------------------------------------------------------
    # PENDING
    # --------------------------------------------------------

    if order_status == "PENDING":

        # Small number of failed demo payments
        if random.random() < 0.15:

            return {
                "advance": "FAILED",
                "final": "LOCKED",
                "overall": "PAYMENT_FAILED"
            }

        return {
            "advance": "PENDING",
            "final": "LOCKED",
            "overall": "PAYMENT_DUE"
        }

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    return {
        "advance": "PENDING",
        "final": "LOCKED",
        "overall": "PAYMENT_DUE"
    }


# ============================================================
# CREATE PAYMENT DOCUMENT
# ============================================================

def create_payment(order, delivery, index):

    total = money(
        order.get("total_amount", 0)
    )

    # Exact 50/50 split
    advance_amount = money(
        total * 0.50
    )

    # Remainder guarantees exact total
    final_amount = money(
        total - advance_amount
    )

    state = get_payment_state(
        order,
        delivery
    )

    created_at = order.get(
        "created_at",
        datetime.now(timezone.utc)
    )

    # --------------------------------------------------------
    # Advance payment
    # --------------------------------------------------------

    advance_paid_at = None

    if state["advance"] == "PAID":

        advance_paid_at = (
            created_at
            + timedelta(
                hours=random.randint(1, 24)
            )
        )

    # --------------------------------------------------------
    # Final payment
    # --------------------------------------------------------

    final_paid_at = None

    if state["final"] == "PAID":

        final_paid_at = (
            created_at
            + timedelta(
                days=random.randint(1, 7)
            )
        )

    # --------------------------------------------------------
    # Existing financial fields
    # --------------------------------------------------------

    platform_fee = money(
        total * 0.02
    )

    logistics_fee = money(
        random.uniform(150, 1200)
    )

    farmer_payout = money(
        total
        - platform_fee
        - logistics_fee
    )

    # --------------------------------------------------------
    # Seed/demo transaction information
    # --------------------------------------------------------

    payment_method = None
    transaction_reference = None

    if state["advance"] == "PAID":

        payment_method = random.choice([
            "UPI",
            "CARD",
            "BANK_TRANSFER",
            "NET_BANKING"
        ])

        transaction_reference = (
            f"AGRITXN"
            f"{random.randint(10000000, 99999999)}"
        )

    # --------------------------------------------------------
    # PAYMENT DOCUMENT
    # --------------------------------------------------------

    return {

        "payment_id": f"PAY-{index:05d}",

        "order_id": order["order_id"],

        "buyer_id": order["buyer_id"],
        "farmer_id": order["farmer_id"],

        # Useful display information
        "buyer_name": order.get(
            "buyer_name"
        ),

        "buyer_role": order.get(
            "buyer_role"
        ),

        "farmer_name": order.get(
            "farmer_name"
        ),

        "produce_name": order.get(
            "produce_name"
        ),

        "category": order.get(
            "category"
        ),

        "quantity": order.get(
            "quantity"
        ),

        "unit": order.get(
            "unit"
        ),

        "unit_price": order.get(
            "unit_price"
        ),

        # ----------------------------------------------------
        # TOTAL ORDER AMOUNT
        # ----------------------------------------------------

        "amount": total,

        # ----------------------------------------------------
        # FIRST 50%
        # ----------------------------------------------------

        "advance_payment": {

            "amount": advance_amount,

            "status": state["advance"],

            # Real Razorpay values will be inserted
            # when an actual payment is made.
            "razorpay_order_id": None,

            "razorpay_payment_id": None,

            "razorpay_signature": None,

            "paid_at": advance_paid_at
        },

        # ----------------------------------------------------
        # SECOND 50%
        # ----------------------------------------------------

        "final_payment": {

            "amount": final_amount,

            "status": state["final"],

            "razorpay_order_id": None,

            "razorpay_payment_id": None,

            "razorpay_signature": None,

            "paid_at": final_paid_at
        },

        # ----------------------------------------------------
        # OVERALL
        # ----------------------------------------------------

        "overall_status": state["overall"],

        # ----------------------------------------------------
        # Existing financial information
        # ----------------------------------------------------

        "platform_fee": platform_fee,

        "logistics_fee": logistics_fee,

        "farmer_payout": farmer_payout,

        "payment_method": payment_method,

        "transaction_reference": transaction_reference,

        # ----------------------------------------------------
        # Useful references
        # ----------------------------------------------------

        "order_status": order.get(
            "status"
        ),

        "delivery_status": (
            delivery.get("status")
            if delivery
            else None
        ),

        "created_at": created_at,

        "seed_batch": SEED_BATCH
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print(" AgriCentre - Payment Collection Rebuilder")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # Get EXISTING orders
    # --------------------------------------------------------

    orders = list(
        orders_col.find({
            "seed_batch": SEED_BATCH
        })
    )

    print(
        f"Existing orders found: {len(orders)}"
    )

    if not orders:

        print()
        print(
            "ERROR: No existing seeded orders found."
        )
        print(
            "Nothing was changed."
        )

        return

    # --------------------------------------------------------
    # Safety confirmation
    # --------------------------------------------------------

    print()
    print(
        "This script will ONLY replace payment records"
    )

    print(
        f"with seed_batch = '{SEED_BATCH}'."
    )

    print()
    print(
        "Orders, deliveries, users and produce "
        "will NOT be modified."
    )

    print()

    confirm = input(
        "Type REBUILD to continue: "
    ).strip()

    if confirm != "REBUILD":

        print()
        print(
            "Cancelled. Nothing was changed."
        )

        return

    # --------------------------------------------------------
    # Delete existing seeded payments
    # --------------------------------------------------------

    delete_result = payments_col.delete_many({
        "seed_batch": SEED_BATCH
    })

    print()
    print(
        f"Old seeded payments deleted: "
        f"{delete_result.deleted_count}"
    )

    # --------------------------------------------------------
    # Generate new payments
    # --------------------------------------------------------

    payments = []

    for index, order in enumerate(
        orders,
        start=1
    ):

        delivery = get_delivery(
            order["order_id"]
        )

        payment = create_payment(
            order,
            delivery,
            index
        )

        payments.append(payment)

    # --------------------------------------------------------
    # Insert new payments
    # --------------------------------------------------------

    if payments:

        insert_result = (
            payments_col.insert_many(
                payments
            )
        )

        print(
            f"New payments created: "
            f"{len(insert_result.inserted_ids)}"
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    counts = {}

    for payment in payments:

        status = payment[
            "overall_status"
        ]

        counts[status] = (
            counts.get(status, 0) + 1
        )

    print()
    print("=" * 60)
    print(" PAYMENT SUMMARY")
    print("=" * 60)

    for status, count in sorted(
        counts.items()
    ):

        print(
            f"{status:<25} {count}"
        )

    # --------------------------------------------------------
    # Validate 50/50 amounts
    # --------------------------------------------------------

    invalid = []

    for payment in payments:

        total = payment["amount"]

        advance = payment[
            "advance_payment"
        ]["amount"]

        final = payment[
            "final_payment"
        ]["amount"]

        if money(
            advance + final
        ) != money(total):

            invalid.append(
                payment["order_id"]
            )

    print()

    if invalid:

        print(
            f"WARNING: {len(invalid)} "
            "payment amounts are invalid."
        )

    else:

        print(
            "✓ 50/50 payment amounts validated."
        )

    print()
    print("=" * 60)
    print(" DONE")
    print("=" * 60)
    print()
    print(
        "✓ Orders untouched"
    )
    print(
        "✓ Deliveries untouched"
    )
    print(
        "✓ Users untouched"
    )
    print(
        "✓ Produce untouched"
    )
    print(
        "✓ Payments rebuilt"
    )
    print()


if __name__ == "__main__":
    main()
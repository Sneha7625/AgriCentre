from flask import Blueprint, jsonify, current_app, request
from datetime import datetime, timezone
from bson import ObjectId
import razorpay

from routes.auth_routes import token_required
from utils.email_service import send_email


payment_bp = Blueprint(
    "payment",
    __name__,
    url_prefix="/api/payments"
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    return current_app.config["DB"]


# ============================================================
# AUTH / BUYER
# ============================================================

def get_current_buyer():

    db = get_db()

    try:
        user_id = ObjectId(request.user_id)
    except Exception:
        return None

    user = db["users"].find_one({
        "_id": user_id
    })

    if not user:
        return None

    role = str(
        user.get("role", "")
    ).strip().upper()

    if role not in {
        "WHOLESALER",
        "BULK_BUYER",
        "BULK BUYER",
        "VENDOR"
    }:
        return None

    return user


# ============================================================
# HELPERS
# ============================================================

def oid_variants(value):

    values = [value]

    try:
        values.append(
            ObjectId(str(value))
        )
    except Exception:
        pass

    return values


def money(value):

    try:
        return round(
            float(value or 0),
            2
        )

    except (
        TypeError,
        ValueError
    ):
        return 0.0


def serial(value):

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    return value


# ============================================================
# RAZORPAY CLIENT
# ============================================================

def get_razorpay_client():

    key_id = current_app.config.get(
        "RAZORPAY_KEY_ID"
    )

    key_secret = current_app.config.get(
        "RAZORPAY_KEY_SECRET"
    )

    if not key_id or not key_secret:

        raise RuntimeError(
            "Razorpay API keys are not configured."
        )

    return razorpay.Client(
        auth=(
            key_id,
            key_secret
        )
    )


# ============================================================
# PAYMENT SERIALIZATION
# ============================================================

def serialize_payment(payment):

    advance = payment.get(
        "advance_payment",
        {}
    )

    final = payment.get(
        "final_payment",
        {}
    )

    return {

        "id": serial(
            payment.get("_id")
        ),

        "payment_id": payment.get(
            "payment_id",
            ""
        ),

        "order_id": payment.get(
            "order_id",
            ""
        ),

        "buyer_id": serial(
            payment.get("buyer_id")
        ),

        "buyer_name": payment.get(
            "buyer_name",
            ""
        ),

        "buyer_role": payment.get(
            "buyer_role",
            ""
        ),

        "farmer_id": serial(
            payment.get("farmer_id")
        ),

        "farmer_name": payment.get(
            "farmer_name",
            ""
        ),

        "produce_name": payment.get(
            "produce_name",
            ""
        ),

        "category": payment.get(
            "category",
            ""
        ),

        "quantity": payment.get(
            "quantity",
            0
        ),

        "unit": payment.get(
            "unit",
            "KG"
        ),

        "unit_price": money(
            payment.get("unit_price")
        ),

        "amount": money(
            payment.get("amount")
        ),

        "advance_payment": {
            "amount": money(
                advance.get("amount")
            ),
            "status": advance.get(
                "status",
                "PENDING"
            ),
            "razorpay_order_id": advance.get(
                "razorpay_order_id"
            ),
            "razorpay_payment_id": advance.get(
                "razorpay_payment_id"
            ),
            "paid_at": serial(
                advance.get("paid_at")
            )
        },

        "final_payment": {
            "amount": money(
                final.get("amount")
            ),
            "status": final.get(
                "status",
                "LOCKED"
            ),
            "razorpay_order_id": final.get(
                "razorpay_order_id"
            ),
            "razorpay_payment_id": final.get(
                "razorpay_payment_id"
            ),
            "paid_at": serial(
                final.get("paid_at")
            )
        },

        "overall_status": payment.get(
            "overall_status",
            "PAYMENT_DUE"
        ),

        "order_status": payment.get(
            "order_status"
        ),

        "delivery_status": payment.get(
            "delivery_status"
        ),

        "platform_fee": money(
            payment.get("platform_fee")
        ),

        "logistics_fee": money(
            payment.get("logistics_fee")
        ),

        "farmer_payout": money(
            payment.get("farmer_payout")
        ),

        "payment_method": payment.get(
            "payment_method"
        ),

        "transaction_reference": payment.get(
            "transaction_reference"
        ),

        "created_at": serial(
            payment.get("created_at")
        )
    }


# ============================================================
# UPDATE OVERALL STATUS
# ============================================================

def calculate_overall_status(payment):

    advance_status = payment.get(
        "advance_payment",
        {}
    ).get(
        "status",
        "PENDING"
    )

    final_status = payment.get(
        "final_payment",
        {}
    ).get(
        "status",
        "LOCKED"
    )

    if final_status == "PAID":

        return "COMPLETELY_PAID"

    if advance_status == "PAID" and final_status == "PENDING":

        return "FINAL_PAYMENT_DUE"

    if advance_status == "PAID":

        return "ADVANCE_PAID"

    if advance_status == "FAILED":

        return "PAYMENT_FAILED"

    return "PAYMENT_DUE"


# ============================================================
# GET DELIVERY STATUS
# ============================================================

def get_delivery_status(order_id):

    db = get_db()

    delivery = db["deliveries"].find_one(
        {
            "order_id": order_id
        },
        sort=[
            ("created_at", -1)
        ]
    )

    if not delivery:

        return None

    return str(
        delivery.get(
            "status",
            ""
        )
    ).upper()


# ============================================================
# GET PAYMENT RECORDS
# ============================================================

@payment_bp.route(
    "",
    methods=["GET"]
)
@token_required
def get_payments():

    buyer = get_current_buyer()

    if not buyer:

        return jsonify({
            "success": False,
            "message": (
                "Only buyer or bulk buyer "
                "accounts can access payments."
            )
        }), 403

    try:

        db = get_db()

        buyer_ids = {
            "$in": oid_variants(
                buyer["_id"]
            )
        }

        payments = list(
            db["payments"].find({
                "buyer_id": buyer_ids
            }).sort(
                "created_at",
                -1
            )
        )

        result = []

        for payment in payments:

            # ------------------------------------------------
            # Keep delivery status fresh
            # ------------------------------------------------

            delivery_status = get_delivery_status(
                payment.get("order_id")
            )

            if delivery_status:

                payment["delivery_status"] = (
                    delivery_status
                )

                # Final payment becomes available ONLY
                # after delivery.
                if (
                    delivery_status == "DELIVERED"
                    and payment.get(
                        "advance_payment",
                        {}
                    ).get(
                        "status"
                    ) == "PAID"
                    and payment.get(
                        "final_payment",
                        {}
                    ).get(
                        "status"
                    ) == "LOCKED"
                ):

                    payment[
                        "final_payment"
                    ]["status"] = "PENDING"

                    payment[
                        "overall_status"
                    ] = "FINAL_PAYMENT_DUE"

                    db["payments"].update_one(
                        {
                            "_id": payment["_id"]
                        },
                        {
                            "$set": {
                                "delivery_status":
                                    delivery_status,

                                "final_payment.status":
                                    "PENDING",

                                "overall_status":
                                    "FINAL_PAYMENT_DUE"
                            }
                        }
                    )

            result.append(
                serialize_payment(
                    payment
                )
            )

        # ----------------------------------------------------
        # Stats
        # ----------------------------------------------------

        total_orders = len(result)

        total_amount = sum(
            money(p["amount"])
            for p in result
        )

        paid_amount = 0

        remaining_amount = 0

        advance_paid_count = 0

        final_due_count = 0

        completely_paid_count = 0

        payment_due_count = 0

        failed_count = 0

        for p in result:

            advance = p[
                "advance_payment"
            ]

            final = p[
                "final_payment"
            ]

            if advance["status"] == "PAID":

                paid_amount += advance[
                    "amount"
                ]

                advance_paid_count += 1

            if final["status"] == "PAID":

                paid_amount += final[
                    "amount"
                ]

            else:

                if final["status"] == "PENDING":

                    remaining_amount += final[
                        "amount"
                    ]

            if p["overall_status"] == "FINAL_PAYMENT_DUE":

                final_due_count += 1

            elif p["overall_status"] == "COMPLETELY_PAID":

                completely_paid_count += 1

            elif p["overall_status"] == "PAYMENT_DUE":

                remaining_amount += advance[
                    "amount"
                ]

                payment_due_count += 1

            elif p["overall_status"] == "PAYMENT_FAILED":

                remaining_amount += advance[
                    "amount"
                ]

                failed_count += 1

        return jsonify({

            "success": True,

            "payments": result,

            "count": total_orders,

            "stats": {

                "total_orders": total_orders,

                "total_amount": money(
                    total_amount
                ),

                "paid_amount": money(
                    paid_amount
                ),

                "remaining_amount": money(
                    remaining_amount
                ),

                "advance_paid_count":
                    advance_paid_count,

                "final_due_count":
                    final_due_count,

                "completely_paid_count":
                    completely_paid_count,

                "payment_due_count":
                    payment_due_count,

                "failed_count":
                    failed_count
            }

        }), 200

    except Exception as e:

        current_app.logger.exception(
            "Error loading payments"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load payments.",
            "error": str(e)
        }), 500


# ============================================================
# GET ONE PAYMENT / ORDER DETAILS
# ============================================================

@payment_bp.route(
    "/<order_id>",
    methods=["GET"]
)
@token_required
def get_payment_details(order_id):

    buyer = get_current_buyer()

    if not buyer:

        return jsonify({
            "success": False,
            "message": "Unauthorized."
        }), 403

    try:

        db = get_db()

        buyer_ids = {
            "$in": oid_variants(
                buyer["_id"]
            )
        }

        payment = db["payments"].find_one({
            "order_id": order_id,
            "buyer_id": buyer_ids
        })

        if not payment:

            return jsonify({
                "success": False,
                "message": "Payment record not found."
            }), 404

        delivery_status = get_delivery_status(
            order_id
        )

        if delivery_status:

            payment["delivery_status"] = (
                delivery_status
            )

        return jsonify({

            "success": True,

            "payment": serialize_payment(
                payment
            )

        }), 200

    except Exception as e:

        current_app.logger.exception(
            "Error loading payment details"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load payment details.",
            "error": str(e)
        }), 500


# ============================================================
# CREATE RAZORPAY ORDER
# ============================================================

@payment_bp.route(
    "/order/<order_id>/create",
    methods=["POST"]
)
@token_required
def create_payment_order(order_id):

    buyer = get_current_buyer()

    if not buyer:

        return jsonify({
            "success": False,
            "message": "Unauthorized."
        }), 403

    try:

        db = get_db()

        buyer_ids = {
            "$in": oid_variants(
                buyer["_id"]
            )
        }

        order = db["orders"].find_one({

            "order_id": order_id,

            "buyer_id": buyer_ids

        })

        if not order:

            return jsonify({
                "success": False,
                "message": "Order not found."
            }), 404

        payment = db["payments"].find_one({

            "order_id": order_id,

            "buyer_id": buyer_ids

        })

        if not payment:

            return jsonify({
                "success": False,
                "message": (
                    "Payment record does not exist "
                    "for this order."
                )
            }), 404

        data = request.get_json(
            silent=True
        ) or {}

        payment_type = str(
            data.get(
                "payment_type",
                "advance"
            )
        ).strip().lower()

        # ----------------------------------------------------
        # Determine amount
        # ----------------------------------------------------

        if payment_type == "advance":

            payment_info = payment.get(
                "advance_payment",
                {}
            )

            amount = money(
                payment_info.get(
                    "amount"
                )
            )

            status = payment_info.get(
                "status"
            )

        elif payment_type == "final":

            # ------------------------------------------------
            # FINAL PAYMENT MUST REQUIRE DELIVERY
            # ------------------------------------------------

            delivery_status = get_delivery_status(
                order_id
            )

            if delivery_status != "DELIVERED":

                return jsonify({
                    "success": False,
                    "message": (
                        "Final payment is available "
                        "only after the order is delivered."
                    )
                }), 400

            advance_status = payment.get(
                "advance_payment",
                {}
            ).get(
                "status"
            )

            if advance_status != "PAID":

                return jsonify({
                    "success": False,
                    "message": (
                        "Advance payment must be completed "
                        "before the final payment."
                    )
                }), 400

            payment_info = payment.get(
                "final_payment",
                {}
            )

            amount = money(
                payment_info.get(
                    "amount"
                )
            )

            status = payment_info.get(
                "status"
            )

        else:

            return jsonify({
                "success": False,
                "message": "Invalid payment type."
            }), 400

        if status == "PAID":

            return jsonify({
                "success": False,
                "message": (
                    "This payment stage "
                    "is already paid."
                )
            }), 400

        if status == "LOCKED":

            return jsonify({
                "success": False,
                "message": (
                    "This payment stage "
                    "is currently locked."
                )
            }), 400

        if amount <= 0:

            return jsonify({
                "success": False,
                "message": (
                    "Invalid payment amount."
                )
            }), 400

        # ----------------------------------------------------
        # Create Razorpay order
        # ----------------------------------------------------

        client = get_razorpay_client()

        razorpay_order = client.order.create({

            "amount": int(
                round(
                    amount * 100
                )
            ),

            "currency": "INR",

            "receipt": (
                f"{order_id}-"
                f"{payment_type}"
            ),

            "notes": {

                "agricentre_order_id":
                    order_id,

                "payment_type":
                    payment_type,

                "buyer_id":
                    str(
                        buyer["_id"]
                    )
            }
        })

        razorpay_order_id = (
            razorpay_order["id"]
        )

        # ----------------------------------------------------
        # Save Razorpay order ID
        # ----------------------------------------------------

        field_prefix = (
            "advance_payment"
            if payment_type == "advance"
            else "final_payment"
        )

        db["payments"].update_one(

            {
                "_id":
                    payment["_id"]
            },

            {
                "$set": {

                    f"{field_prefix}.razorpay_order_id":
                        razorpay_order_id,

                    "updated_at":
                        datetime.now(
                            timezone.utc
                        )
                }
            }
        )

        return jsonify({

            "success": True,

            "key_id":
                current_app.config[
                    "RAZORPAY_KEY_ID"
                ],

            "razorpay_order_id":
                razorpay_order_id,

            "amount":
                amount,

            "currency":
                "INR",

            "payment_type":
                payment_type,

            "order_id":
                order_id

        }), 200

    except Exception as e:

        current_app.logger.exception(
            "Error creating Razorpay order"
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to create payment order.",

            "error":
                str(e)

        }), 500


# ============================================================
# VERIFY RAZORPAY PAYMENT
# ============================================================

@payment_bp.route(
    "/verify",
    methods=["POST"]
)
@token_required
def verify_payment():

    buyer = get_current_buyer()

    if not buyer:

        return jsonify({
            "success": False,
            "message": "Unauthorized."
        }), 403

    try:

        db = get_db()

        data = request.get_json(
            silent=True
        ) or {}

        order_id = data.get(
            "order_id"
        )

        payment_type = str(
            data.get(
                "payment_type",
                ""
            )
        ).strip().lower()

        razorpay_order_id = data.get(
            "razorpay_order_id"
        )

        razorpay_payment_id = data.get(
            "razorpay_payment_id"
        )

        razorpay_signature = data.get(
            "razorpay_signature"
        )

        if not all([
            order_id,
            payment_type,
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature
        ]):

            return jsonify({
                "success": False,
                "message": (
                    "Incomplete payment information."
                )
            }), 400

        buyer_ids = {
            "$in": oid_variants(
                buyer["_id"]
            )
        }

        payment = db["payments"].find_one({

            "order_id": order_id,

            "buyer_id": buyer_ids

        })

        if not payment:

            return jsonify({
                "success": False,
                "message": "Payment record not found."
            }), 404

        # ----------------------------------------------------
        # Verify Razorpay signature
        # ----------------------------------------------------

        client = get_razorpay_client()

        client.utility.verify_payment_signature({

            "razorpay_order_id":
                razorpay_order_id,

            "razorpay_payment_id":
                razorpay_payment_id,

            "razorpay_signature":
                razorpay_signature
        })

        now = datetime.now(
            timezone.utc
        )

        # ----------------------------------------------------
        # Update correct payment stage
        # ----------------------------------------------------

        if payment_type == "advance":

            prefix = "advance_payment"

        elif payment_type == "final":

            # Re-check delivery on backend
            delivery_status = get_delivery_status(
                order_id
            )

            if delivery_status != "DELIVERED":

                return jsonify({
                    "success": False,
                    "message": (
                        "Final payment cannot be "
                        "completed before delivery."
                    )
                }), 400

            prefix = "final_payment"

        else:

            return jsonify({
                "success": False,
                "message": "Invalid payment type."
            }), 400

        update_fields = {

            f"{prefix}.status":
                "PAID",

            f"{prefix}.razorpay_order_id":
                razorpay_order_id,

            f"{prefix}.razorpay_payment_id":
                razorpay_payment_id,

            f"{prefix}.razorpay_signature":
                razorpay_signature,

            f"{prefix}.paid_at":
                now,

            "updated_at":
                now
        }

        # ----------------------------------------------------
        # Recalculate overall status
        # ----------------------------------------------------

        payment_copy = dict(
            payment
        )

        if payment_type == "advance":

            payment_copy[
                "advance_payment"
            ] = dict(
                payment_copy.get(
                    "advance_payment",
                    {}
                )
            )

            payment_copy[
                "advance_payment"
            ]["status"] = "PAID"

        else:

            payment_copy[
                "final_payment"
            ] = dict(
                payment_copy.get(
                    "final_payment",
                    {}
                )
            )

            payment_copy[
                "final_payment"
            ]["status"] = "PAID"

        overall_status = (
            calculate_overall_status(
                payment_copy
            )
        )

        update_fields[
            "overall_status"
        ] = overall_status

        # ----------------------------------------------------
        # Update DB
        # ----------------------------------------------------

        db["payments"].update_one(

            {
                "_id":
                    payment["_id"]
            },

            {
                "$set":
                    update_fields
            }
        )

        saved = db[
            "payments"
        ].find_one({
            "_id":
                payment["_id"]
        })

        # ----------------------------------------------------
        # Send farmer email
        # ----------------------------------------------------

        farmer_id = saved.get(
            "farmer_id"
        )

        farmer = None

        if farmer_id:

            try:

                farmer = db[
                    "users"
                ].find_one({
                    "_id":
                        ObjectId(
                            str(
                                farmer_id
                            )
                        )
                })

            except Exception:

                farmer = db[
                    "users"
                ].find_one({
                    "_id":
                        farmer_id
                })

        email_sent = False

        if farmer and farmer.get(
            "email"
        ):

            farmer_email = farmer[
                "email"
            ]

            farmer_name = farmer.get(
                "name",
                "Farmer"
            )

            buyer_name = saved.get(
                "buyer_name",
                buyer.get(
                    "name",
                    "Buyer"
                )
            )

            amount_paid = money(
                saved.get(
                    prefix,
                    {}
                ).get(
                    "amount"
                )
            )

            if payment_type == "advance":

                payment_label = (
                    "50% Advance Payment"
                )

            else:

                payment_label = (
                    "50% Final Payment"
                )

            remaining = 0

            advance_status = saved.get(
                "advance_payment",
                {}
            ).get(
                "status"
            )

            final_status = saved.get(
                "final_payment",
                {}
            ).get(
                "status"
            )

            if advance_status != "PAID":

                remaining += money(
                    saved.get(
                        "advance_payment",
                        {}
                    ).get(
                        "amount"
                    )
                )

            if final_status != "PAID":

                remaining += money(
                    saved.get(
                        "final_payment",
                        {}
                    ).get(
                        "amount"
                    )
                )

            subject = (
                "AgriCentre - "
                f"{payment_label} Received "
                f"for Order {order_id}"
            )

            body = f"""
Hello {farmer_name},

A payment has been successfully made for an AgriCentre order.

Order ID: {order_id}
Buyer: {buyer_name}

Payment Type: {payment_label}
Amount Received: ₹{amount_paid:,.2f}

Total Order Amount: ₹{money(saved.get("amount")):,.2f}

Remaining Amount: ₹{remaining:,.2f}

Payment Reference:{razorpay_payment_id}

Payment Date:{now.strftime("%d %B %Y, %I:%M %p UTC")}

Please check your AgriCentre account for more details.

Regards,
AgriCentre
"""

            html_body = f"""
<html>
<body style="font-family:Arial,sans-serif;line-height:1.6;">

<h2>AgriCentre - Payment Received</h2>

<p>Hello {farmer_name},</p>

<p>
A payment has been successfully made for an AgriCentre order.
</p>

<table cellpadding="8" cellspacing="0"
       style="border-collapse:collapse;">

<tr>
<td><strong>Order ID</strong></td>
<td>{order_id}</td>
</tr>

<tr>
<td><strong>Buyer</strong></td>
<td>{buyer_name}</td>
</tr>

<tr>
<td><strong>Payment Type</strong></td>
<td>{payment_label}</td>
</tr>

<tr>
<td><strong>Amount Received</strong></td>
<td>₹{amount_paid:,.2f}</td>
</tr>

<tr>
<td><strong>Total Order</strong></td>
<td>₹{money(saved.get("amount")):,.2f}</td>
</tr>

<tr>
<td><strong>Remaining</strong></td>
<td>₹{remaining:,.2f}</td>
</tr>

<tr>
<td><strong>Payment Reference</strong></td>
<td>{razorpay_payment_id}</td>
</tr>

</table>
<p>
Please check your AgriCentre account for more details.
</p>

<p>Regards,<br>AgriCentre</p>

</body>
</html>
"""

            email_sent = send_email(
                farmer_email,
                subject,
                body,
                html_body
            )

        return jsonify({

            "success": True,

            "message": (
                "Payment verified successfully."
            ),

            "payment": serialize_payment(
                saved
            ),

            "email_sent":
                email_sent

        }), 200

    except razorpay.errors.SignatureVerificationError:

        current_app.logger.exception(
            "Razorpay signature verification failed"
        )

        return jsonify({

            "success": False,

            "message": (
                "Payment verification failed."
            )

        }), 400

    except Exception as e:

        current_app.logger.exception(
            "Error verifying Razorpay payment"
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to verify payment.",

            "error":
                str(e)

        }), 500
from flask import Blueprint, jsonify, current_app, request
from datetime import datetime
from bson import ObjectId

from routes.auth_routes import token_required

# ============================================================
# ORDER BLUEPRINT
# ============================================================

order_bp = Blueprint(
    "order",
    __name__
)


# ============================================================
# HELPERS
# ============================================================

def get_db():
    return current_app.config["DB"]


def get_current_farmer():
    """
    Get the authenticated farmer from the JWT user_id.

    We NEVER accept farmer_id from the frontend.
    """

    db = get_db()

    try:

        user_id = ObjectId(
            request.user_id
        )

    except Exception:

        return None


    farmer = db["users"].find_one({
        "_id": user_id
    })


    if not farmer:
        return None


    role = str(
        farmer.get("role", "")
    ).strip().upper()


    if role != "FARMER":
        return None


    return farmer


# ============================================================
# SERIALIZE ORDER
# ============================================================

def serialize_order(order):
    """
    Convert MongoDB order document into JSON-safe data.
    """

    def serialize_value(value):

        if isinstance(
            value,
            ObjectId
        ):

            return str(value)


        if isinstance(
            value,
            datetime
        ):

            return value.isoformat()


        return value


    return {

        # ----------------------------------------------------
        # IDENTIFICATION
        # ----------------------------------------------------

        "id":
            str(order["_id"])
            if order.get("_id")
            else None,

        "order_id":
            order.get(
                "order_id",
                ""
            ),

        "listing_id":
            order.get(
                "listing_id",
                ""
            ),


        # ----------------------------------------------------
        # BUYER
        # ----------------------------------------------------

        "buyer_id":
            serialize_value(
                order.get("buyer_id")
            ),

        "buyer_name":
            order.get(
                "buyer_name",
                ""
            ),

        "buyer_role":
            order.get(
                "buyer_role",
                ""
            ),


        # ----------------------------------------------------
        # FARMER
        # ----------------------------------------------------

        "farmer_id":
            serialize_value(
                order.get("farmer_id")
            ),

        "farmer_name":
            order.get(
                "farmer_name",
                ""
            ),


        # ----------------------------------------------------
        # PRODUCE
        # ----------------------------------------------------

        "produce_name":
            order.get(
                "produce_name",
                ""
            ),

        "category":
            order.get(
                "category",
                ""
            ),


        # ----------------------------------------------------
        # QUANTITY
        # ----------------------------------------------------

        "quantity":
            order.get(
                "quantity",
                0
            ),

        "unit":
            order.get(
                "unit",
                ""
            ),


        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        "unit_price":
            order.get(
                "unit_price",
                0
            ),

        "total_amount":
            order.get(
                "total_amount",
                0
            ),


        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        "status":
            order.get(
                "status",
                "PENDING"
            ),


        # ----------------------------------------------------
        # DATES
        # ----------------------------------------------------

        "created_at":
            serialize_value(
                order.get("created_at")
            ),

        "expected_delivery":
            serialize_value(
                order.get(
                    "expected_delivery"
                )
            )
    }
# ============================================================
# GET BUYER ORDERS / OFFER HISTORY
#
# GET /api/orders/buyer
#
# Used by:
#   - VENDOR
#   - WHOLESALER
#   - BULK_BUYER
#   - BULK BUYER
#
# This combines:
#   1. Actual orders
#   2. Pending/Declined offers
#
# Accepted offers are matched with their created order so
# they are NOT displayed twice.
# ============================================================

@order_bp.route(
    "/api/orders/buyer",
    methods=["GET"]
)
@token_required
def get_buyer_orders():

    db = get_db()

    # ========================================================
    # 1. GET LOGGED-IN USER
    # ========================================================

    try:

        user_id = ObjectId(
            request.user_id
        )

    except Exception:

        return jsonify({
            "success": False,
            "message": "Invalid user session."
        }), 401


    buyer = db["users"].find_one({
        "_id": user_id
    })


    if not buyer:

        return jsonify({
            "success": False,
            "message": "Buyer account not found."
        }), 404


    # ========================================================
    # 2. VERIFY BUYER / BULK BUYER
    # ========================================================

    role = str(
        buyer.get("role", "")
    ).strip().upper()


    allowed_roles = {
        "VENDOR",
        "WHOLESALER",
        "BULK_BUYER",
        "BULK BUYER"
    }


    if role not in allowed_roles:

        return jsonify({
            "success": False,
            "message": (
                "Only Buyer and Bulk Buyer accounts "
                "can access buyer orders."
            )
        }), 403


    # ========================================================
    # 3. BUYER ID QUERY
    #
    # Some existing documents may contain buyer_id as:
    #   ObjectId
    # or
    #   string
    #
    # So support both.
    # ========================================================

    buyer_id_query = {
        "$in": [
            buyer["_id"],
            str(buyer["_id"])
        ]
    }


    # ========================================================
    # 4. GET ACTUAL ORDERS
    # ========================================================

    try:

        orders = list(
            db["orders"]
            .find({
                "buyer_id": buyer_id_query
            })
            .sort(
                "created_at",
                -1
            )
        )

    except Exception as error:

        current_app.logger.exception(
            "Unable to fetch buyer orders."
        )

        return jsonify({
            "success": False,
            "message": "Unable to load buyer orders."
        }), 500


    # ========================================================
    # 5. GET BUYER OFFERS
    #
    # This is important because DECLINED and PENDING offers
    # are stored in the offers collection, not orders.
    # ========================================================

    try:

        offers = list(
            db["offers"]
            .find({
                "buyer_id": buyer_id_query
            })
            .sort(
                "created_at",
                -1
            )
        )

    except Exception as error:

        current_app.logger.exception(
            "Unable to fetch buyer offers."
        )

        return jsonify({
            "success": False,
            "message": "Unable to load buyer offer history."
        }), 500


    # ========================================================
    # 6. SERIALIZE ACTUAL ORDERS
    # ========================================================

    serialized_orders = []

    matched_offer_ids = set()


    for order in orders:

        serialized = serialize_order(
            order
        )

        offer_id = order.get(
            "offer_id"
        )


        # ----------------------------------------------------
        # Find the corresponding offer.
        #
        # This lets us display ACCEPTED instead of PENDING
        # for an order that was just created from an accepted
        # offer.
        # ----------------------------------------------------

        matching_offer = None

        if offer_id:

            matching_offer = next(
                (
                    offer
                    for offer in offers
                    if offer.get("offer_id") == offer_id
                ),
                None
            )


        if matching_offer:

            matched_offer_ids.add(
                str(
                    matching_offer.get(
                        "_id"
                    )
                )
            )


            offer_status = str(
                matching_offer.get(
                    "status",
                    ""
                )
            ).strip().upper()


            order_status = str(
                serialized.get(
                    "status",
                    "PENDING"
                )
            ).strip().upper()


            # If the order is still at its initial PENDING
            # state but the offer was accepted, show ACCEPTED
            # to the buyer.
            if (
                order_status == "PENDING"
                and offer_status == "ACCEPTED"
            ):

                serialized["status"] = "ACCEPTED"


        serialized_orders.append(
            serialized
        )


    # ========================================================
    # 7. ADD PENDING / DECLINED OFFERS
    #
    # Accepted offers that already have an order are skipped.
    #
    # Pending and Declined offers remain visible.
    # ========================================================

    for offer in offers:

        offer_db_id = str(
            offer.get("_id")
        )


        if offer_db_id in matched_offer_ids:

            continue


        offer_status = str(
            offer.get(
                "status",
                "PENDING"
            )
        ).strip().upper()


        # ----------------------------------------------------
        # Buyer history entry for an offer
        # ----------------------------------------------------

        offer_entry = {

            "id":
                offer_db_id,

            "order_id":
                offer.get(
                    "offer_id",
                    ""
                ),

            "offer_id":
                offer.get(
                    "offer_id",
                    ""
                ),

            "listing_id":
                offer.get(
                    "listing_id",
                    ""
                ),

            "buyer_id":
                str(
                    buyer["_id"]
                ),

            "buyer_name":
                offer.get(
                    "buyer_name",
                    buyer.get(
                        "name",
                        "Buyer"
                    )
                ),

            "buyer_role":
                offer.get(
                    "buyer_role",
                    role
                ),

            "farmer_id":
                str(
                    offer.get(
                        "farmer_id",
                        ""
                    )
                ),

            "farmer_name":
                offer.get(
                    "farmer_name",
                    "Farmer"
                ),

            "produce_name":
                offer.get(
                    "produce_name",
                    "Produce"
                ),

            "category":
                offer.get(
                    "category",
                    ""
                ),

            "quantity":
                offer.get(
                    "quantity",
                    0
                ),

            "unit":
                offer.get(
                    "unit",
                    ""
                ),

            "unit_price":
                offer.get(
                    "offered_price",
                    0
                ),

            "offered_price":
                offer.get(
                    "offered_price",
                    0
                ),

            "total_amount":
                offer.get(
                    "total_amount",
                    0
                ),

            "status":
                offer_status,

            "created_at":
                serialize_order({
                    "created_at":
                        offer.get(
                            "created_at"
                        )
                })["created_at"],

            "expected_delivery":
                None,

            "is_offer":
                True
        }


        serialized_orders.append(
            offer_entry
        )


    # ========================================================
    # 8. SORT EVERYTHING TOGETHER
    #
    # Newest activity appears first.
    # ========================================================

    serialized_orders.sort(
        key=lambda item: (
            item.get("created_at")
            or ""
        ),
        reverse=True
    )


    # ========================================================
    # 9. SUMMARY
    # ========================================================

    total = len(
        serialized_orders
    )


    pending = sum(
        1
        for item in serialized_orders
        if str(
            item.get(
                "status",
                ""
            )
        ).upper() == "PENDING"
    )


    accepted = sum(
        1
        for item in serialized_orders
        if str(
            item.get(
                "status",
                ""
            )
        ).upper() == "ACCEPTED"
    )


    declined = sum(
        1
        for item in serialized_orders
        if str(
            item.get(
                "status",
                ""
            )
        ).upper() == "DECLINED"
    )


    processing = sum(
        1
        for item in serialized_orders
        if str(
            item.get(
                "status",
                ""
            )
        ).upper() == "PROCESSING"
    )


    shipped = sum(
        1
        for item in serialized_orders
        if str(
            item.get(
                "status",
                ""
            )
        ).upper()
        in {
            "SHIPPED",
            "IN_TRANSIT"
        }
    )


    delivered = sum(
        1
        for item in serialized_orders
        if str(
            item.get(
                "status",
                ""
            )
        ).upper()
        in {
            "DELIVERED",
            "COMPLETED"
        }
    )


    # ========================================================
    # 10. RESPONSE
    # ========================================================

    return jsonify({

        "success": True,

        "count":
            total,

        "orders":
            serialized_orders,

        "summary": {

            "total":
                total,

            "pending":
                pending,

            "accepted":
                accepted,

            "declined":
                declined,

            "processing":
                processing,

            "shipped":
                shipped,

            "delivered":
                delivered
        }

    }), 200

# ============================================================
# GET FARMER ORDERS
#
# GET /api/orders/farmer
#
# IMPORTANT:
# This endpoint returns ORDERS only.
# It does NOT return offers.
# ============================================================

@order_bp.route(
    "/api/orders/farmer",
    methods=["GET"]
)
@token_required
def get_farmer_orders():

    db = get_db()


    # ========================================================
    # 1. VERIFY FARMER
    # ========================================================

    farmer = get_current_farmer()


    if not farmer:

        return jsonify({

            "success": False,

            "message":
                "Only Farmer accounts can view orders."

        }), 403


    # ========================================================
    # 2. GET FARMER ID
    # ========================================================

    farmer_id = farmer["_id"]


    # ========================================================
    # 3. OPTIONAL STATUS FILTER
    #
    # The frontend can send:
    #
    # /api/orders/farmer?status=PENDING
    #
    # But by default we return all orders.
    # ========================================================

    status = request.args.get(
        "status",
        ""
    ).strip().upper()


    query = {

        "farmer_id":
            farmer_id
    }


    allowed_statuses = {
        "PENDING",
        "CONFIRMED",
        "PROCESSING",
        "SHIPPED",
        "DELIVERED",
        "CANCELLED"
    }


    if status:

        if status not in allowed_statuses:

            return jsonify({

                "success": False,

                "message":
                    "Invalid order status."

            }), 400


        query["status"] = status


    # ========================================================
    # 4. FETCH ORDERS
    #
    # IMPORTANT:
    # We query ONLY the "orders" collection.
    #
    # Offers are stored separately in:
    # db["offers"]
    #
    # They are NEVER included here.
    # ========================================================

    try:

        orders = list(

            db["orders"]
            .find(query)
            .sort(
                "created_at",
                -1
            )

        )

    except Exception as error:

        current_app.logger.exception(
            "Unable to fetch farmer orders."
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to load orders."

        }), 500


    # ========================================================
    # 5. SERIALIZE
    # ========================================================

    serialized_orders = [

        serialize_order(order)

        for order in orders

    ]


    # ========================================================
    # 6. CALCULATE SUMMARY
    #
    # Summary is calculated from the actual MongoDB orders
    # returned for this farmer.
    # ========================================================

    total_orders = len(
        serialized_orders
    )


    pending_orders = sum(

        1

        for order in serialized_orders

        if order["status"] == "PENDING"

    )


    in_progress_orders = sum(

        1

        for order in serialized_orders

        if order["status"]
        in {
            "CONFIRMED",
            "PROCESSING",
            "SHIPPED"
        }

    )


    completed_orders = sum(

        1

        for order in serialized_orders

        if order["status"] == "DELIVERED"

    )


    cancelled_orders = sum(

        1

        for order in serialized_orders

        if order["status"] == "CANCELLED"

    )


    total_value = sum(

        float(
            order["total_amount"] or 0
        )

        for order in serialized_orders

    )


    # ========================================================
    # 7. RESPONSE
    # ========================================================

    return jsonify({

        "success": True,

        "count":
            total_orders,

        "orders":
            serialized_orders,

        "summary": {

            "total_orders":
                total_orders,

            "pending":
                pending_orders,

            "in_progress":
                in_progress_orders,

            "completed":
                completed_orders,

            "cancelled":
                cancelled_orders,

            "total_value":
                round(
                    total_value,
                    2
                )
        }

    }), 200


# ============================================================
# GET SINGLE FARMER ORDER
#
# GET /api/orders/farmer/<order_id>
#
# This is also farmer-only.
# A farmer can only open an order belonging to them.
# ============================================================

@order_bp.route(
    "/api/orders/farmer/<order_id>",
    methods=["GET"]
)
@token_required
def get_farmer_order(
    order_id
):

    db = get_db()


    # ========================================================
    # 1. VERIFY FARMER
    # ========================================================

    farmer = get_current_farmer()


    if not farmer:

        return jsonify({

            "success": False,

            "message":
                "Only Farmer accounts can view orders."

        }), 403


    # ========================================================
    # 2. FIND ORDER
    #
    # Notice:
    #
    # farmer_id + order_id
    #
    # This prevents a farmer from requesting another
    # farmer's order just by knowing its order ID.
    # ========================================================

    order = db["orders"].find_one({

        "order_id":
            order_id,

        "farmer_id":
            farmer["_id"]

    })


    if not order:

        return jsonify({

            "success": False,

            "message":
                "Order not found."

        }), 404


    # ========================================================
    # 3. RETURN ORDER
    # ========================================================

    return jsonify({

        "success": True,

        "order":
            serialize_order(order)

    }), 200
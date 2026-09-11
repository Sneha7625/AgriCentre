from flask import Blueprint, jsonify, request, current_app
from bson import ObjectId
from datetime import datetime


dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/api/dashboard"
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    return current_app.config["DB"]


# ============================================================
# HELPERS
# ============================================================

def get_user_id():

    user_id = request.headers.get("X-User-ID")

    if not user_id:
        return None

    try:
        return ObjectId(user_id)

    except Exception:
        return None


def serialize(value):

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, list):
        return [serialize(v) for v in value]

    if isinstance(value, dict):
        return {
            key: serialize(val)
            for key, val in value.items()
        }

    return value


def money(value):

    try:
        return round(float(value or 0), 2)

    except (TypeError, ValueError):
        return 0


# ============================================================
# FARMER DASHBOARD
# ============================================================

def farmer_dashboard(db, user_id):

    listings = list(
        db["produce"].find({
            "farmer_id": user_id,
            "status": "ACTIVE"
        })
    )

    orders = list(
        db["orders"].find({
            "farmer_id": user_id
        }).sort(
            "created_at",
            -1
        )
    )

    offers = list(
        db["offers"].find({
            "farmer_id": user_id
        }).sort(
            "created_at",
            -1
        )
    )

    payments = list(
        db["payments"].find({
            "farmer_id": user_id,
            "status": "PAID"
        })
    )

    earnings = sum(
        money(
            payment.get(
                "farmer_payout",
                payment.get("amount", 0)
            )
        )
        for payment in payments
    )

    # --------------------------------------------------------
    # RECENT ORDERS
    # --------------------------------------------------------

    recent_orders = []

    for order in orders[:5]:

        recent_orders.append({
            "order_id": order.get("order_id"),

            "produce_name":
                order.get("produce_name"),

            "buyer_name":
                order.get("buyer_name"),

            "quantity":
                order.get("quantity", 0),

            "unit":
                order.get("unit", ""),

            "total_amount":
                money(order.get("total_amount")),

            "status":
                order.get("status", "PENDING"),

            "created_at":
                serialize(order.get("created_at"))
        })

    # --------------------------------------------------------
    # RECENT OFFERS
    # --------------------------------------------------------

    recent_offers = []

    for offer in offers[:5]:

        recent_offers.append({
            "offer_id":
                offer.get("offer_id"),

            "produce_name":
                offer.get("produce_name"),

            "buyer_name":
                offer.get("buyer_name"),

            "quantity":
                offer.get("quantity", 0),

            "unit":
                offer.get("unit", ""),

            "listed_price":
                money(
                    offer.get("listed_price")
                ),

            "offered_price":
                money(
                    offer.get("offered_price")
                ),

            "status":
                offer.get("status", "PENDING"),

            "created_at":
                serialize(
                    offer.get("created_at")
                )
        })

    # --------------------------------------------------------
    # QUALITY
    # --------------------------------------------------------

    quality_checks = list(
        db["quality_checks"].find({
            "farmer_id": user_id
        }).sort(
            "checked_at",
            -1
        )
    )

    quality = {
        "total": len(quality_checks),

        "passed": sum(
            1
            for q in quality_checks
            if q.get("result") == "PASS"
        ),

        "review": sum(
            1
            for q in quality_checks
            if q.get("result") == "REVIEW"
        ),

        "failed": sum(
            1
            for q in quality_checks
            if q.get("result") == "FAIL"
        )
    }

    # --------------------------------------------------------
    # MARKET INSIGHTS
    # --------------------------------------------------------

    farmer_crops = list({
        listing.get("produce_name")
        for listing in db["produce"].find(
            {"farmer_id": user_id},
            {"produce_name": 1}
        )
        if listing.get("produce_name")
    })

    market_insights = []

    if farmer_crops:

        market_records = list(
            db["market_data"].find({
                "crop": {
                    "$in": farmer_crops
                }
            }).sort(
                "date",
                -1
            ).limit(20)
        )

        for record in market_records[:8]:

            market_insights.append({
                "crop":
                    record.get("crop"),

                "market":
                    record.get("market"),

                "price":
                    money(record.get("price")),

                "demand_quantity":
                    record.get(
                        "demand_quantity",
                        0
                    ),

                "supply_quantity":
                    record.get(
                        "supply_quantity",
                        0
                    ),

                "demand_level":
                    record.get(
                        "demand_level"
                    ),

                "date":
                    serialize(
                        record.get("date")
                    )
            })

    return {

        "role": "FARMER",

        "stats": {

            "active_listings":
                len(listings),

            "orders":
                len(orders),

            "offers":
                len(offers),

            "earnings":
                earnings
        },

        "recent_orders":
            recent_orders,

        "recent_offers":
            recent_offers,

        "quality":
            quality,

        "market_insights":
            market_insights
    }


# ============================================================
# WHOLESALER DASHBOARD
# ============================================================

def wholesaler_dashboard(db, user_id):

    orders = list(
        db["orders"].find({
            "buyer_id": user_id,
            "buyer_role": "WHOLESALER"
        }).sort(
            "created_at",
            -1
        )
    )

    offers = list(
        db["offers"].find({
            "buyer_id": user_id,
            "buyer_role": "WHOLESALER"
        }).sort(
            "created_at",
            -1
        )
    )

    deliveries = list(
        db["deliveries"].find({
            "buyer_id": user_id
        })
    )

    payments = list(
        db["payments"].find({
            "buyer_id": user_id
        })
    )

    favorites = list(
        db["favorites"].find({
            "user_id": user_id
        })
    )

    total_payments = sum(
        money(payment.get("amount"))
        for payment in payments
        if payment.get("status") == "PAID"
    )

    recent_orders = []

    for order in orders[:5]:

        recent_orders.append({
            "order_id":
                order.get("order_id"),

            "produce_name":
                order.get("produce_name"),

            "farmer_name":
                order.get("farmer_name"),

            "quantity":
                order.get("quantity", 0),

            "unit":
                order.get("unit", ""),

            "total_amount":
                money(
                    order.get("total_amount")
                ),

            "status":
                order.get(
                    "status",
                    "PENDING"
                ),

            "created_at":
                serialize(
                    order.get("created_at")
                )
        })

    recent_offers = []

    for offer in offers[:5]:

        recent_offers.append({
            "offer_id":
                offer.get("offer_id"),

            "produce_name":
                offer.get("produce_name"),

            "offered_price":
                money(
                    offer.get("offered_price")
                ),

            "quantity":
                offer.get("quantity", 0),

            "unit":
                offer.get("unit", ""),

            "status":
                offer.get(
                    "status",
                    "PENDING"
                ),

            "created_at":
                serialize(
                    offer.get("created_at")
                )
        })

    return {

        "role":
            "WHOLESALER",

        "stats": {

            "active_orders":
                len([
                    order
                    for order in orders
                    if order.get("status")
                    not in [
                        "DELIVERED",
                        "CANCELLED"
                    ]
                ]),

            "total_orders":
                len(orders),

            "offers":
                len(offers),

            "deliveries":
                len(deliveries),

            "favorites":
                len(favorites),

            "payments":
                total_payments
        },

        "recent_orders":
            recent_orders,

        "recent_offers":
            recent_offers
    }


# ============================================================
# VENDOR DASHBOARD
# ============================================================

def vendor_dashboard(db, user_id):

    orders = list(
        db["orders"].find({
            "buyer_id": user_id,
            "buyer_role": "VENDOR"
        }).sort(
            "created_at",
            -1
        )
    )

    offers = list(
        db["offers"].find({
            "buyer_id": user_id,
            "buyer_role": "VENDOR"
        }).sort(
            "created_at",
            -1
        )
    )

    deliveries = list(
        db["deliveries"].find({
            "buyer_id": user_id
        })
    )

    payments = list(
        db["payments"].find({
            "buyer_id": user_id
        })
    )

    favorites = list(
        db["favorites"].find({
            "user_id": user_id
        })
    )

    total_payments = sum(
        money(payment.get("amount"))
        for payment in payments
        if payment.get("status") == "PAID"
    )

    recent_orders = []

    for order in orders[:5]:

        recent_orders.append({
            "order_id":
                order.get("order_id"),

            "produce_name":
                order.get("produce_name"),

            "farmer_name":
                order.get("farmer_name"),

            "quantity":
                order.get("quantity", 0),

            "unit":
                order.get("unit", ""),

            "total_amount":
                money(
                    order.get("total_amount")
                ),

            "status":
                order.get(
                    "status",
                    "PENDING"
                ),

            "created_at":
                serialize(
                    order.get("created_at")
                )
        })

    recent_offers = []

    for offer in offers[:5]:

        recent_offers.append({
            "offer_id":
                offer.get("offer_id"),

            "produce_name":
                offer.get("produce_name"),

            "offered_price":
                money(
                    offer.get("offered_price")
                ),

            "quantity":
                offer.get("quantity", 0),

            "unit":
                offer.get("unit", ""),

            "status":
                offer.get(
                    "status",
                    "PENDING"
                ),

            "created_at":
                serialize(
                    offer.get("created_at")
                )
        })

    return {

        "role":
            "VENDOR",

        "stats": {

            "active_orders":
                len([
                    order
                    for order in orders
                    if order.get("status")
                    not in [
                        "DELIVERED",
                        "CANCELLED"
                    ]
                ]),

            "total_orders":
                len(orders),

            "offers":
                len(offers),

            "deliveries":
                len(deliveries),

            "favorites":
                len(favorites),

            "payments":
                total_payments
        },

        "recent_orders":
            recent_orders,

        "recent_offers":
            recent_offers
    }


# ============================================================
# MAIN DASHBOARD API
# ============================================================

@dashboard_bp.route("", methods=["GET"])
def get_dashboard():

    db = get_db()

    user_id = get_user_id()

    if not user_id:

        return jsonify({
            "success": False,
            "message":
                "User authentication required."
        }), 401


    user = db["users"].find_one({
        "_id": user_id
    })


    if not user:

        return jsonify({
            "success": False,
            "message":
                "User not found."
        }), 404


    role = str(
        user.get("role", "")
    ).upper()


    if role == "FARMER":

        dashboard = farmer_dashboard(
            db,
            user_id
        )

    elif role == "WHOLESALER":

        dashboard = wholesaler_dashboard(
            db,
            user_id
        )

    elif role == "VENDOR":

        dashboard = vendor_dashboard(
            db,
            user_id
        )

    else:

        return jsonify({
            "success": False,
            "message": "Unsupported user role."
        }), 400


    return jsonify({

        "success": True,

        "user": {

            "id":
                str(user["_id"]),

            "name":
                user.get("name"),

            "email":
                user.get("email"),

            "role":
                role
        },

        "dashboard":
            serialize(dashboard)

    }), 200
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from bson import ObjectId
import uuid
from routes.auth_routes import token_required
from utils.email_service import send_email
from routes.auth_routes import token_required
from datetime import datetime, timezone, timedelta
from utils.email_service import send_email

offer_bp = Blueprint(
    "offer",
    __name__,
    url_prefix="/api/offers"
)


# ============================================================
# HELPERS
# ============================================================

def get_db():
    return current_app.config["DB"]

# ============================================================
# CREATE OFFER
# POST /api/offers/create
#
# Buyer submits an offer from Cart.
# ============================================================

@offer_bp.route(
    "/create",
    methods=["POST"]
)
@token_required
def create_offer():

    db = get_db()

    # --------------------------------------------------------
    # CURRENT USER
    # --------------------------------------------------------

    try:
        buyer_id = ObjectId(
            request.user_id
        )
    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid user session."
        }), 401

    buyer = db["users"].find_one({
        "_id": buyer_id
    })

    if not buyer:
        return jsonify({
            "success": False,
            "message": "Buyer account not found."
        }), 404

    buyer_role = str(
        buyer.get("role", "")
    ).strip().upper()

    if buyer_role not in {
        "VENDOR",
        "WHOLESALER",
        "BULK_BUYER",
        "BULK BUYER"
    }:
        return jsonify({
            "success": False,
            "message": (
                "Only Buyer and Bulk Buyer accounts "
                "can submit offers."
            )
        }), 403

    # --------------------------------------------------------
    # REQUEST DATA
    # --------------------------------------------------------

    data = request.get_json() or {}

    listing_id = str(
        data.get(
            "listing_id",
            ""
        )
    ).strip()

    notes = str(
        data.get(
            "notes",
            ""
        )
    ).strip()

    # --------------------------------------------------------
    # QUANTITY
    # --------------------------------------------------------

    try:
        quantity = float(
            data.get(
                "quantity",
                0
            )
        )
    except (
        TypeError,
        ValueError
    ):
        quantity = 0

    if quantity <= 0:
        return jsonify({
            "success": False,
            "message": "Quantity must be greater than zero."
        }), 400

    # --------------------------------------------------------
    # OFFERED PRICE
    #
    # This is PRICE PER KG / UNIT.
    # --------------------------------------------------------

    try:
        offered_price = float(
            data.get(
                "offered_price",
                0
            )
        )
    except (
        TypeError,
        ValueError
    ):
        offered_price = 0

    if offered_price <= 0:
        return jsonify({
            "success": False,
            "message": "Offered price must be greater than zero."
        }), 400

    # --------------------------------------------------------
    # FIND LISTING
    #
    # Cart stores MongoDB _id.
    # Farmer offer/order system uses listing_id.
    # --------------------------------------------------------

    listing = None

    try:
        listing = db["produce"].find_one({
            "_id": ObjectId(
                listing_id
            )
        })
    except Exception:
        listing = None

    # Fallback for existing custom listing_id records.
    if not listing:
        listing = db["produce"].find_one({
            "listing_id": listing_id
        })

    if not listing:
        return jsonify({
            "success": False,
            "message": "Produce listing not found."
        }), 404

    # --------------------------------------------------------
    # FARMER
    # --------------------------------------------------------

    farmer_id = listing.get(
        "farmer_id"
    )

    try:
        farmer_object_id = ObjectId(
            str(farmer_id)
        )
    except Exception:
        farmer_object_id = None

    farmer = None

    if farmer_object_id:
        farmer = db["users"].find_one({
            "_id": farmer_object_id
        })

    if not farmer:
        farmer = db["users"].find_one({
            "_id": farmer_id
        })

    if not farmer:
        return jsonify({
            "success": False,
            "message": "Farmer account could not be found."
        }), 404

    farmer_email = str(
        farmer.get(
            "email",
            ""
        )
    ).strip()

    farmer_name = (
        listing.get("farmer_name")
        or farmer.get(
            "name",
            "Farmer"
        )
    )

    # --------------------------------------------------------
    # AVAILABLE STOCK
    # --------------------------------------------------------

    try:
        available_quantity = float(
            listing.get(
                "available_quantity",
                listing.get(
                    "quantity",
                    0
                )
            ) or 0
        )
    except (
        TypeError,
        ValueError
    ):
        available_quantity = 0

    if quantity > available_quantity:
        return jsonify({
            "success": False,
            "message": (
                f"Only {available_quantity:g} "
                f"{listing.get('unit', 'KG')} "
                "is currently available."
            )
        }), 409

    # --------------------------------------------------------
    # MOQ
    # --------------------------------------------------------

    try:
        minimum_order_quantity = float(
            listing.get(
                "minimum_order_quantity",
                listing.get(
                    "minimum_order",
                    0
                )
            ) or 0
        )
    except (
        TypeError,
        ValueError
    ):
        minimum_order_quantity = 0

    # Bulk Buyer minimum
    if buyer_role in {
        "WHOLESALER",
        "BULK_BUYER",
        "BULK BUYER"
    }:
        minimum_order_quantity = max(
            minimum_order_quantity,
            100
        )

    if (
        minimum_order_quantity > 0
        and quantity < minimum_order_quantity
    ):
        return jsonify({
            "success": False,
            "message": (
                f"Minimum offer quantity is "
                f"{minimum_order_quantity:g} "
                f"{listing.get('unit', 'KG')}."
            )
        }), 400

    # --------------------------------------------------------
    # TOTAL
    # --------------------------------------------------------

    total_amount = round(
        quantity * offered_price,
        2
    )

    now = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # OFFER ID
    # --------------------------------------------------------

    offer_id = (
        "OFFER-" +
        uuid.uuid4().hex[:8].upper()
    )

    # Make sure it is unique.
    while db["offers"].find_one({
        "offer_id": offer_id
    }):
        offer_id = (
            "OFFER-" +
            uuid.uuid4().hex[:8].upper()
        )

    # --------------------------------------------------------
    # OFFER DOCUMENT
    # --------------------------------------------------------

    offer_document = {

        "offer_id":
            offer_id,

        "listing_id":
            listing.get(
                "listing_id",
                str(listing["_id"])
            ),

        "farmer_id":
            farmer_id,

        "farmer_name":
            farmer_name,

        "buyer_id":
            buyer["_id"],

        "buyer_name":
            buyer.get(
                "name",
                "Buyer"
            ),

        "buyer_email":
            buyer.get(
                "email",
                ""
            ),

        "buyer_role":
            buyer_role,

        "produce_name":
            listing.get(
                "produce_name",
                "Produce"
            ),

        "quantity":
            quantity,

        "unit":
            listing.get(
                "unit",
                "KG"
            ),

        "listed_price":
            float(
                listing.get(
                    "price_per_unit",
                    listing.get(
                        "price",
                        0
                    )
                ) or 0
            ),

        "offered_price":
            offered_price,

        "total_amount":
            total_amount,

        "notes":
            notes,

        "status":
            "PENDING",

        "created_at":
            now,

        "expires_at":
            now + timedelta(
                days=7
            ),

        "negotiation": [

            {
                "actor":
                    "BUYER",

                "price":
                    offered_price,

                "quantity":
                    quantity,

                "timestamp":
                    now
            }

        ]
    }

    # --------------------------------------------------------
    # SAVE OFFER
    # --------------------------------------------------------

    result = db["offers"].insert_one(
        offer_document
    )

    # --------------------------------------------------------
    # EMAIL BUYER
    # --------------------------------------------------------

    buyer_email = str(
        buyer.get(
            "email",
            ""
        )
    ).strip()

    buyer_email_sent = False

    if buyer_email:

        buyer_email_sent = send_email(

            buyer_email,

            "AgriCentre — Offer Submitted",

            f"""
Hello {buyer.get("name", "Buyer")},

Your offer has been submitted successfully on AgriCentre.

OFFER DETAILS
--------------------------------------------------
Offer ID: {offer_id}
Produce: {listing.get("produce_name", "Produce")}
Farmer: {farmer_name}
Quantity: {quantity:g} {listing.get("unit", "KG")}
Your Offer Price: ₹{offered_price:,.2f} per {listing.get("unit", "KG")}
Total Offered Value: ₹{total_amount:,.2f}

Notes:
{notes or "No additional notes."}

Status: PENDING

The farmer will review your offer and can accept or decline it.

Regards,
AgriCentre Team
"""
        )

    # --------------------------------------------------------
    # EMAIL FARMER
    # --------------------------------------------------------

    farmer_email_sent = False

    if farmer_email:

        farmer_email_sent = send_email(

            farmer_email,

            "AgriCentre — New Offer Received",

            f"""
Hello {farmer_name},

You have received a new offer on AgriCentre.

OFFER DETAILS
--------------------------------------------------
Offer ID: {offer_id}
Produce: {listing.get("produce_name", "Produce")}
Buyer: {buyer.get("name", "Buyer")}
Buyer Role: {buyer_role}

Quantity:
{quantity:g} {listing.get("unit", "KG")}

Listed Price:
₹{offer_document["listed_price"]:,.2f} per {listing.get("unit", "KG")}

Offered Price:
₹{offered_price:,.2f} per {listing.get("unit", "KG")}

Total Offered Value:
₹{total_amount:,.2f}

Buyer Notes:
{notes or "No additional notes."}

Status: PENDING

Please open your AgriCentre Offers page to review and
accept or decline this offer.

Regards,
AgriCentre Team
"""
        )

    # --------------------------------------------------------
    # EMAIL AGRICENTRE TEAM
    # --------------------------------------------------------

    admin_email = (
        current_app.config.get(
            "CONTACT_RECEIVER"
        )
        or current_app.config.get(
            "MAIL_USERNAME"
        )
    )

    admin_email_sent = False

    if admin_email:

        admin_email_sent = send_email(

            admin_email,

            "AgriCentre — New Offer Submitted",

            f"""
Hello AgriCentre Team,

A new offer has been submitted on AgriCentre.

OFFER
--------------------------------------------------
Offer ID: {offer_id}
Produce: {listing.get("produce_name", "Produce")}
Farmer: {farmer_name}
Farmer Email: {farmer_email}

Buyer: {buyer.get("name", "Buyer")}
Buyer Email: {buyer_email}
Buyer Role: {buyer_role}

Quantity:
{quantity:g} {listing.get("unit", "KG")}

Listed Price:
₹{offer_document["listed_price"]:,.2f}

Offered Price:
₹{offered_price:,.2f}

Total:
₹{total_amount:,.2f}

Status:
PENDING

The offer has been stored in MongoDB and is awaiting
farmer action.

Regards,
AgriCentre System
"""
        )

    # --------------------------------------------------------
    # EMAIL STATUS
    # --------------------------------------------------------

    sent_count = sum([
        buyer_email_sent,
        farmer_email_sent,
        admin_email_sent
    ])

    if sent_count == 3:
        email_status = "sent"
    elif sent_count > 0:
        email_status = "partial"
    else:
        email_status = "failed"

    db["offers"].update_one(
        {
            "_id":
                result.inserted_id
        },
        {
            "$set": {

                "email_status":
                    email_status,

                "buyer_email_sent":
                    buyer_email_sent,

                "farmer_email_sent":
                    farmer_email_sent,

                "admin_email_sent":
                    admin_email_sent
            }
        }
    )

    return jsonify({

        "success":
            True,

        "message":
            "Offer submitted successfully.",

        "offer":
            serialize_document(
                offer_document
            ),

        "email_status":
            email_status,

        "emails": {

            "buyer":
                buyer_email_sent,

            "farmer":
                farmer_email_sent,

            "admin":
                admin_email_sent
        }

    }), 201
def get_current_farmer():
    """
    Get the authenticated user from the JWT.

    request.user_id is set by token_required().
    We then fetch the actual user from MongoDB and verify
    that the account is a FARMER.
    """

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

    if role != "FARMER":
        return None

    return user


def serialize_value(value):

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, list):
        return [
            serialize_value(item)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            key: serialize_value(val)
            for key, val in value.items()
            if key != "_id"
        }

    return value


def serialize_document(document):

    if not document:
        return None

    result = serialize_value(document)

    result.pop("_id", None)

    return result


def generate_order_id(orders_collection):

    while True:

        order_id = (
            "ORD-" +
            uuid.uuid4().hex[:8].upper()
        )

        exists = orders_collection.find_one({
            "order_id": order_id
        })

        if not exists:
            return order_id


# ============================================================
# GET FARMER OFFERS
# GET /api/offers/farmer
# ============================================================

@offer_bp.route(
    "/farmer",
    methods=["GET"]
)
@token_required
def get_farmer_offers():

    farmer = get_current_farmer()

    if not farmer:

        return jsonify({
            "success": False,
            "message": (
                "Only Farmer accounts can access offers."
            )
        }), 403

    try:

        db = get_db()

        offers_collection = db["offers"]

        farmer_id = farmer["_id"]
        
        offers = list(
            offers_collection.find({
                "farmer_id": {
                    "$in": [
                        farmer_id,
                        str(farmer_id)
                    ]
                }
            }).sort(
                "created_at",
                -1
            )
        )

        return jsonify({
            "success": True,
            "offers": [
                serialize_document(offer)
                for offer in offers
            ],
            "count": len(offers)
        }), 200

    except Exception as e:

        current_app.logger.exception(
            "Error loading farmer offers"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load offers.",
            "error": str(e)
        }), 500
# ============================================================
# GET BUYER OFFERS
# GET /api/offers/buyer
#
# Returns all offers submitted by the logged-in buyer.
# Supports VENDOR / WHOLESALER / BULK_BUYER.
# ============================================================

@offer_bp.route(
    "/buyer",
    methods=["GET"]
)
@token_required
def get_buyer_offers():

    try:

        db = get_db()

        # ----------------------------------------------------
        # CURRENT USER
        # ----------------------------------------------------

        try:
            buyer_id = ObjectId(
                request.user_id
            )
        except Exception:

            return jsonify({
                "success": False,
                "message": "Invalid user session."
            }), 401


        buyer = db["users"].find_one({
            "_id": buyer_id
        })

        if not buyer:

            return jsonify({
                "success": False,
                "message": "Buyer account not found."
            }), 404


        buyer_role = str(
            buyer.get("role", "")
        ).strip().upper()


        # ----------------------------------------------------
        # ONLY BUYER ACCOUNTS
        # ----------------------------------------------------

        if buyer_role not in {
            "VENDOR",
            "WHOLESALER",
            "BULK_BUYER",
            "BULK BUYER"
        }:

            return jsonify({
                "success": False,
                "message":
                    "Only buyer accounts can access My Offers."
            }), 403


        # ----------------------------------------------------
        # FIND OFFERS
        #
        # Existing offers may contain buyer_id as either:
        # ObjectId or string.
        # ----------------------------------------------------

        offers = list(
            db["offers"].find({
                "buyer_id": {
                    "$in": [
                        buyer_id,
                        str(buyer_id)
                    ]
                }
            }).sort(
                "created_at",
                -1
            )
        )


        # ----------------------------------------------------
        # RETURN
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "offers": [
                serialize_document(offer)
                for offer in offers
            ],

            "count":
                len(offers)

        }), 200


    except Exception as e:

        current_app.logger.exception(
            "Error loading buyer offers"
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to load your offers.",

            "error":
                str(e)

        }), 500

# ============================================================
# GET SINGLE OFFER
# GET /api/offers/<offer_id>
# ============================================================

@offer_bp.route(
    "/<offer_id>",
    methods=["GET"]
)
@token_required
def get_single_offer(offer_id):

    farmer = get_current_farmer()

    if not farmer:

        return jsonify({
            "success": False,
            "message": (
                "Only Farmer accounts can access offers."
            )
        }), 403

    try:

        db = get_db()

        offer = db["offers"].find_one({
            "offer_id": offer_id,
            "farmer_id": {
                "$in": [
                    farmer["_id"],
                    str(farmer["_id"])
                ]
            }
        })

        if not offer:

            return jsonify({
                "success": False,
                "message": "Offer not found."
            }), 404

        return jsonify({
            "success": True,
            "offer": serialize_document(offer)
        }), 200

    except Exception as e:

        current_app.logger.exception(
            "Error loading offer"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load offer.",
            "error": str(e)
        }), 500


# ============================================================
# ACCEPT OFFER
# POST /api/offers/<offer_id>/accept
# ============================================================

@offer_bp.route(
    "/<offer_id>/accept",
    methods=["POST"]
)
@token_required
def accept_offer(offer_id):

    farmer = get_current_farmer()

    if not farmer:

        return jsonify({
            "success": False,
            "message": (
                "Only Farmer accounts can accept offers."
            )
        }), 403

    try:

        db = get_db()

        offers_collection = db["offers"]
        orders_collection = db["orders"]

        farmer_id = farmer["_id"]

        
        # ----------------------------------------------------
        # FIND OFFER
        # ----------------------------------------------------

        offer = offers_collection.find_one({
            "offer_id": offer_id,
            "farmer_id": {
                "$in": [
                    farmer_id,
                    str(farmer_id)
                ]
            }
        })

        if not offer:

            return jsonify({
                "success": False,
                "message": "Offer not found."
            }), 404

        # ----------------------------------------------------
        # FIND BUYER
        # ----------------------------------------------------

        buyer_id = offer.get("buyer_id")

        try:
            buyer_object_id = ObjectId(str(buyer_id))
        except Exception:
            buyer_object_id = None

        buyer = None

        if buyer_object_id:
            buyer = db["users"].find_one({
                "_id": buyer_object_id
            })

        if not buyer:
            buyer = db["users"].find_one({
                "_id": buyer_id
            })

        if not buyer:
            return jsonify({
                "success": False,
                "message": "Buyer account could not be found."
            }), 404
        # ----------------------------------------------------
        # CHECK STATUS
        # ----------------------------------------------------

        status = str(
            offer.get(
                "status",
                "PENDING"
            )
        ).strip().upper()

        if status != "PENDING":

            return jsonify({
                "success": False,
                "message": (
                    f"This offer is already {status.lower()}."
                )
            }), 409


        # ----------------------------------------------------
        # VALIDATE DATA
        # ----------------------------------------------------

        required_fields = [
            "listing_id",
            "buyer_id",
            "produce_name",
            "quantity",
            "unit",
            "offered_price"
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in offer
        ]

        if missing_fields:

            return jsonify({
                "success": False,
                "message": (
                    "Offer is missing: " +
                    ", ".join(missing_fields)
                )
            }), 400


        try:

            quantity = float(
                offer["quantity"]
            )

            offered_price = float(
                offer["offered_price"]
            )

        except (TypeError, ValueError):

            return jsonify({
                "success": False,
                "message": "Invalid quantity or offered price."
            }), 400


        if quantity <= 0:

            return jsonify({
                "success": False,
                "message": "Quantity must be greater than zero."
            }), 400


        if offered_price < 0:

            return jsonify({
                "success": False,
                "message": "Offered price cannot be negative."
            }), 400


        # ----------------------------------------------------
        # TOTAL
        # ----------------------------------------------------

        total_amount = round(
            quantity * offered_price,
            2
        )

        # ----------------------------------------------------
        # CHECK LISTING STOCK
        # ----------------------------------------------------

        listing = db["produce"].find_one({
            "listing_id": offer.get("listing_id")
        })

        if not listing:

            return jsonify({
                "success": False,
                "message": "The produce listing no longer exists."
            }), 404


        # Current available quantity
        available_quantity = float(
            listing.get(
                "available_quantity",
                listing.get(
                    "quantity",
                    0
                )
            )
        )


        # Minimum order quantity
        minimum_order_quantity = float(
            listing.get(
                "minimum_order_quantity",
                listing.get(
                    "minimum_order",
                    0
                )
            )
        )


        # ----------------------------------------------------
        # MINIMUM ORDER CHECK
        # ----------------------------------------------------

        if minimum_order_quantity > 0 and quantity < minimum_order_quantity:

            return jsonify({
                "success": False,
                "message": (
                    f"Minimum order quantity is "
                    f"{minimum_order_quantity:g} "
                    f"{offer.get('unit', '')}."
                )
            }), 400


        # ----------------------------------------------------
        # AVAILABLE STOCK CHECK
        # ----------------------------------------------------

        if quantity > available_quantity:

            return jsonify({
                "success": False,
                "message": (
                    f"Only {available_quantity:g} "
                    f"{offer.get('unit', '')} is currently available."
                )
            }), 409


        # ----------------------------------------------------
        # SOLD OUT CHECK
        # ----------------------------------------------------

        if available_quantity <= 0:

            return jsonify({
                "success": False,
                "message": "This produce is sold out."
            }), 409
        now = datetime.now(
            timezone.utc
        )
        

        # ----------------------------------------------------
        # CREATE ORDER
        # ----------------------------------------------------
        # ----------------------------------------------------
        # ATOMIC STOCK UPDATE
        # ----------------------------------------------------
        #
        # This prevents two buyers from buying the same
        # remaining quantity at the same time.
        #

        stock_update = db["produce"].update_one(
            {
                "listing_id": offer.get("listing_id"),

                "available_quantity": {
                    "$gte": quantity
                }
            },
            {
                "$inc": {
                    "available_quantity": -quantity,
                    "sold_quantity": quantity,
                    "orders_count": 1
                }
            }
        )


        if stock_update.modified_count == 0:

            return jsonify({
                "success": False,
                "message": (
                    "The requested quantity is no longer "
                    "available. Please refresh the listing."
                )
            }), 409
        order_document = {

            "order_id":
                generate_order_id(
                    orders_collection
                ),

            "offer_id":
                offer.get("offer_id"),

            "buyer_id":
            buyer["_id"],

            "buyer_name":
                buyer.get("name", "Unknown Buyer"),

            "buyer_role":
                buyer.get("role", ""),

            "farmer_id":
                offer.get("farmer_id"),

            "farmer_name":
                offer.get(
                    "farmer_name",
                    farmer.get("name")
                ),

            "listing_id":
                offer.get("listing_id"),

            "produce_name":
                offer.get("produce_name"),

            "quantity":
                quantity,

            "unit":
                offer.get("unit"),

            "unit_price":
                offered_price,

            "total_amount":
                total_amount,

            "status":
                "PENDING",

            "created_at":
                now,

            "expected_delivery":
                None,

            "seed_batch":
                offer.get(
                    "seed_batch",
                    "agricentre-demo-v1"
                )
        }


        # ----------------------------------------------------
        # INSERT ORDER
        # ----------------------------------------------------

        orders_collection.insert_one(
            order_document
        )


        # ----------------------------------------------------
        # MARK OFFER ACCEPTED
        # ----------------------------------------------------

        update_result = offers_collection.update_one(
            {
                "_id": offer["_id"],
                "status": "PENDING"
            },
            {
                "$set": {
                    "status": "ACCEPTED",
                    "accepted_at": now
                }
            }
        )


        # ----------------------------------------------------
        # SAFETY ROLLBACK
        # ----------------------------------------------------

        if update_result.modified_count == 0:

            # Delete the order if it was already inserted
            orders_collection.delete_one({
                "order_id":
                    order_document["order_id"]
            })

            # Return the reserved quantity to the listing
            db["produce"].update_one(
                {
                    "listing_id":
                        offer.get("listing_id")
                },
                {
                    "$inc": {
                        "available_quantity":
                            quantity,

                        "sold_quantity":
                            -quantity,

                        "orders_count":
                            -1
                    }
                }
            )

            return jsonify({
                "success": False,
                "message":
                    "Offer was already processed."
            }), 409

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        # --------------------------------------------------------
        # MARK LOCAL OFFER OBJECT AS ACCEPTED
        # --------------------------------------------------------

        offer["status"] = "ACCEPTED"
        offer["accepted_at"] = now


        # --------------------------------------------------------
        # SEND ACCEPTANCE EMAIL TO BUYER
        # --------------------------------------------------------

        email_sent = False

        try:

            buyer_id = offer.get("buyer_id")

            buyer = None

            # Buyer ID may be stored as ObjectId or string.
            try:
                buyer_object_id = ObjectId(
                    str(buyer_id)
                )
            except Exception:
                buyer_object_id = None

            if buyer_object_id:

                buyer = db["users"].find_one({
                    "_id": buyer_object_id
                })

            if not buyer:

                buyer = db["users"].find_one({
                    "_id": buyer_id
                })

            buyer_email = (
                buyer.get("email", "").strip()
                if buyer
                else ""
            )

            buyer_name = (
                buyer.get("name")
                if buyer
                else offer.get(
                    "buyer_name",
                    "Buyer"
                )
            )

            if buyer_email:

                email_subject = (
                    "AgriCentre — Your Offer Has Been Accepted"
                )

                email_body = f"""
        Hello {buyer_name},

        Great news! Your offer has been accepted by the farmer.

        ORDER DETAILS
        --------------------------------------------------

        Order ID:
        {order_document["order_id"]}

        Produce:
        {order_document["produce_name"]}

        Farmer:
        {order_document["farmer_name"]}

        Quantity:
        {quantity:g} {order_document["unit"]}

        Agreed Price:
        ₹{offered_price:,.2f} per {order_document["unit"]}

        Total Amount:
        ₹{total_amount:,.2f}

        Order Status:
        {order_document["status"]}

        --------------------------------------------------

        Your order has been successfully created on AgriCentre.

        You can now open "My Orders" from your AgriCentre dashboard
        to view the order and follow its delivery progress.

        Regards,
        AgriCentre Team
        """

                email_sent = send_email(
                    buyer_email,
                    email_subject,
                    email_body
                )

            else:

                current_app.logger.warning(
                    "Offer accepted but buyer email was not found. "
                    "Offer ID: %s",
                    offer_id
                )

        except Exception as email_error:

            # IMPORTANT:
            # Email failure must NOT undo a successful order.
            current_app.logger.exception(
                "Buyer acceptance email failed for offer %s: %s",
                offer_id,
                email_error
            )


        return jsonify({

            "success": True,

            "message":
                "Offer accepted and order created successfully.",

            "email_sent":
                email_sent,

            "offer":
                serialize_document(offer),

            "order":
                serialize_document(order_document)

        }), 200
    except Exception as e:

        current_app.logger.exception(
            "Error accepting offer"
        )

        return jsonify({
            "success": False,
            "message": "Unable to accept offer.",
            "error": str(e)
        }), 500


# ============================================================
# DECLINE OFFER
# POST /api/offers/<offer_id>/decline
# ============================================================

@offer_bp.route(
    "/<offer_id>/decline",
    methods=["POST"]
)
@token_required
def decline_offer(offer_id):

    farmer = get_current_farmer()

    if not farmer:

        return jsonify({
            "success": False,
            "message": (
                "Only Farmer accounts can decline offers."
            )
        }), 403

    try:

        db = get_db()

        offers_collection = db["offers"]

        offer = offers_collection.find_one({
            "offer_id": offer_id,
            "farmer_id": {
                "$in": [
                    farmer["_id"],
                    str(farmer["_id"])
                ]
            }
        })

        if not offer:

            return jsonify({
                "success": False,
                "message": "Offer not found."
            }), 404


        # ----------------------------------------------------
        # ONLY PENDING CAN BE DECLINED
        # ----------------------------------------------------

        status = str(
            offer.get(
                "status",
                "PENDING"
            )
        ).strip().upper()

        if status != "PENDING":

            return jsonify({
                "success": False,
                "message": (
                    f"This offer is already {status.lower()}."
                )
            }), 409


        now = datetime.now(
            timezone.utc
        )


        # ----------------------------------------------------
        # IMPORTANT:
        # We DO NOT delete the offer.
        # It remains visible as DECLINED.
        # ----------------------------------------------------

        result = offers_collection.update_one(
            {
                "_id": offer["_id"],
                "status": "PENDING"
            },
            {
                "$set": {
                    "status": "DECLINED",
                    "declined_at": now
                }
            }
        )


        if result.modified_count == 0:

            return jsonify({
                "success": False,
                "message": (
                    "Offer was already processed."
                )
            }), 409


        offer["status"] = "DECLINED"
        offer["declined_at"] = now


        return jsonify({

            "success": True,

            "message":
                "Offer declined successfully.",

            "offer":
                serialize_document(offer)

        }), 200


    except Exception as e:

        current_app.logger.exception(
            "Error declining offer"
        )

        return jsonify({
            "success": False,
            "message": "Unable to decline offer.",
            "error": str(e)
        }), 500


# ============================================================
# OFFER COUNTS
# GET /api/offers/farmer/counts
# ============================================================

@offer_bp.route(
    "/farmer/counts",
    methods=["GET"]
)
@token_required
def get_offer_counts():

    farmer = get_current_farmer()

    if not farmer:

        return jsonify({
            "success": False,
            "message": (
                "Only Farmer accounts can access offers."
            )
        }), 403

    try:

        db = get_db()

        collection = db["offers"]

        farmer_query = {
            "farmer_id": {
                "$in": [
                    farmer["_id"],
                    str(farmer["_id"])
                ]
            }
        }


        total = collection.count_documents(
            farmer_query
        )

        pending = collection.count_documents({
            **farmer_query,
            "status": "PENDING"
        })

        accepted = collection.count_documents({
            **farmer_query,
            "status": "ACCEPTED"
        })

        declined = collection.count_documents({
            **farmer_query,
            "status": "DECLINED"
        })


        return jsonify({

            "success": True,

            "counts": {
                "total": total,
                "pending": pending,
                "accepted": accepted,
                "declined": declined
            }

        }), 200


    except Exception as e:

        current_app.logger.exception(
            "Error loading offer counts"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load offer counts.",
            "error": str(e)
        }), 500
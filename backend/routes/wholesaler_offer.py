from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId

from routes.auth_routes import token_required


# ============================================================
# BLUEPRINT
# ============================================================

wholesaler_offer_bp = Blueprint(
    "wholesaler_offer",
    __name__,
    url_prefix="/api/wholesaler-offers"
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    return current_app.config["DB"]


# ============================================================
# SERIALIZATION
# ============================================================

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


# ============================================================
# GET CURRENT WHOLESALER
# ============================================================

def get_current_wholesaler():

    db = get_db()

    try:

        user_id = ObjectId(
            request.user_id
        )

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
        "BULK BUYER"
    }:

        return None


    return user


# ============================================================
# GET WHOLESALER OFFERS
#
# GET /api/wholesaler-offers
#
# Returns only offers submitted by the logged-in wholesaler.
# ============================================================

@wholesaler_offer_bp.route(
    "",
    methods=["GET"]
)
@token_required
def get_wholesaler_offers():

    wholesaler = get_current_wholesaler()


    if not wholesaler:

        return jsonify({

            "success": False,

            "message":
                "Only Wholesaler / Bulk Buyer accounts "
                "can access My Offers."

        }), 403


    try:

        db = get_db()


        # ----------------------------------------------------
        # WHOLESALER ID
        # ----------------------------------------------------

        wholesaler_id = wholesaler["_id"]


        # ----------------------------------------------------
        # SUPPORT OLD DATA
        #
        # buyer_id may exist as ObjectId or string.
        # ----------------------------------------------------

        buyer_query = {
            "buyer_id": {
                "$in": [
                    wholesaler_id,
                    str(wholesaler_id)
                ]
            }
        }


        # ----------------------------------------------------
        # OPTIONAL STATUS FILTER
        #
        # Example:
        # /api/wholesaler-offers?status=PENDING
        # ----------------------------------------------------

        status = str(
            request.args.get(
                "status",
                ""
            )
        ).strip().upper()


        if status in {
            "PENDING",
            "ACCEPTED",
            "DECLINED"
        }:

            buyer_query["status"] = status


        # ----------------------------------------------------
        # SEARCH
        #
        # Example:
        # /api/wholesaler-offers?search=tomato
        # ----------------------------------------------------

        search = str(
            request.args.get(
                "search",
                ""
            )
        ).strip()


        if search:

            buyer_query["$or"] = [

                {
                    "produce_name": {
                        "$regex": search,
                        "$options": "i"
                    }
                },

                {
                    "farmer_name": {
                        "$regex": search,
                        "$options": "i"
                    }
                },

                {
                    "offer_id": {
                        "$regex": search,
                        "$options": "i"
                    }
                }

            ]


        # ----------------------------------------------------
        # FETCH
        # ----------------------------------------------------

        offers = list(
            db["offers"]
            .find(buyer_query)
            .sort(
                "created_at",
                -1
            )
        )


        # ----------------------------------------------------
        # SERIALIZE
        # ----------------------------------------------------

       # ----------------------------------------------------
        # SERIALIZE + RESOLVE FARMER NAME
        # ----------------------------------------------------

        serialized_offers = []

        for offer in offers:

            serialized = serialize_document(offer)

            # ------------------------------------------------
            # FARMER NAME
            #
            # New offers may already contain farmer_name.
            # For older offers, resolve it using farmer_id.
            # ------------------------------------------------

            farmer_name = serialized.get("farmer_name")

            if not farmer_name:

                farmer_id = offer.get("farmer_id")

                farmer = None

                # Try ObjectId
                if farmer_id:

                    try:

                        farmer_object_id = (
                            farmer_id
                            if isinstance(farmer_id, ObjectId)
                            else ObjectId(str(farmer_id))
                        )

                        farmer = db["users"].find_one({
                            "_id": farmer_object_id
                        })

                    except Exception:

                        farmer = None

                # If farmer_id didn't resolve, try string ID
                if not farmer and farmer_id:

                    farmer = db["users"].find_one({
                        "_id": str(farmer_id)
                    })

                # Extract farmer name
                if farmer:

                    farmer_name = (
                        farmer.get("name")
                        or farmer.get("full_name")
                        or farmer.get("username")
                        or "Unknown Farmer"
                    )

                else:

                    farmer_name = "Unknown Farmer"

            serialized["farmer_name"] = farmer_name

            serialized_offers.append(serialized)


        # ----------------------------------------------------
        # COUNTS
        #
        # Counts are calculated from ALL offers belonging
        # to this wholesaler, not from the filtered result.
        # ----------------------------------------------------

        base_query = {

            "buyer_id": {
                "$in": [
                    wholesaler_id,
                    str(wholesaler_id)
                ]
            }

        }


        total = db["offers"].count_documents(
            base_query
        )


        pending = db["offers"].count_documents({

            **base_query,

            "status": "PENDING"

        })


        accepted = db["offers"].count_documents({

            **base_query,

            "status": "ACCEPTED"

        })


        declined = db["offers"].count_documents({

            **base_query,

            "status": "DECLINED"

        })


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "offers":
                serialized_offers,

            "count":
                len(serialized_offers),

            "stats": {

                "total":
                    total,

                "pending":
                    pending,

                "accepted":
                    accepted,

                "declined":
                    declined

            }

        }), 200


    except Exception as e:

        current_app.logger.exception(
            "Error loading wholesaler offers"
        )


        return jsonify({

            "success": False,

            "message":
                "Unable to load wholesaler offers.",

            "error":
                str(e)

        }), 500
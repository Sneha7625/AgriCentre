from flask import Blueprint, jsonify, current_app, request
from bson import ObjectId
from routes.auth_routes import token_required
from utils.email_service import send_email
import math
import requests
import time


buyer_bp = Blueprint(
    "buyer",
    __name__
)


# ============================================================
# DATABASE
# ============================================================

def get_db():

    return current_app.config["DB"]


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user():

    db = get_db()

    try:

        user_id = ObjectId(
            request.user_id
        )

    except Exception:

        return None

    return db["users"].find_one({
        "_id": user_id
    })


# ============================================================
# SAFE FLOAT
# ============================================================

def safe_float(value):

    try:

        value = float(value)

        if math.isfinite(value):

            return value

    except (
        TypeError,
        ValueError
    ):

        pass

    return None


# ============================================================
# GEOCODE LOCATION
#
# Uses OpenStreetMap Nominatim.
#
# Coordinates are cached in MongoDB so we don't repeatedly
# call the geocoding service for the same user.
# ============================================================
def geocode_user(user):

    db = get_db()

    # --------------------------------------------------------
    # 1. Check cached coordinates
    # --------------------------------------------------------

    lat = safe_float(
        user.get("latitude", user.get("lat"))
    )

    lon = safe_float(
        user.get(
            "longitude",
            user.get("lng", user.get("lon"))
        )
    )

    if lat is not None and lon is not None:
        return lat, lon

    # --------------------------------------------------------
    # 2. Get address
    # --------------------------------------------------------

    address = str(
        user.get("address")
        or user.get("location")
        or ""
    ).strip()

    if not address:
        print(
            "NO ADDRESS FOR USER:",
            user.get("name")
        )
        return None, None

    # --------------------------------------------------------
    # 3. Try the complete address first
    # --------------------------------------------------------

    queries = [
        f"{address}, India"
    ]

    # --------------------------------------------------------
    # 4. Also extract city/state from address
    #
    # Seed data format:
    # Village Khera, Hisar, Haryana
    # Wholesale Market Road, Surat, Gujarat
    # Main Market, Amritsar, Punjab
    # --------------------------------------------------------

    parts = [
        p.strip()
        for p in address.split(",")
        if p.strip()
    ]

    if len(parts) >= 2:

        # Last part = state
        state = parts[-1]

        # Second-last = city
        city = parts[-2]

        queries.append(
            f"{city}, {state}, India"
        )

        queries.append(
            f"{city}, India"
        )

    # Remove duplicate queries
    queries = list(dict.fromkeys(queries))

    # --------------------------------------------------------
    # 5. Geocode using Nominatim
    # --------------------------------------------------------

    for query in queries:

        try:

            print(
                "GEOCODING:",
                user.get("name"),
                "->",
                query
            )

            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "in"
                },
                headers={
                    "User-Agent":
                        "AgriCentre-SIH2026/1.0"
                },
                timeout=10
            )

            print(
                "GEOCODE STATUS:",
                response.status_code
            )

            if response.status_code != 200:
                continue

            results = response.json()

            if not results:
                continue

            lat = safe_float(
                results[0].get("lat")
            )

            lon = safe_float(
                results[0].get("lon")
            )

            if lat is None or lon is None:
                continue

            # ------------------------------------------------
            # Save coordinates permanently
            # ------------------------------------------------

            db["users"].update_one(
                {
                    "_id": user["_id"]
                },
                {
                    "$set": {
                        "latitude": lat,
                        "longitude": lon
                    }
                }
            )

            print(
                "GEOCODED:",
                user.get("name"),
                lat,
                lon
            )

            time.sleep(1)

            return lat, lon

        except Exception as e:

            print(
                "GEOCODING ERROR:",
                query,
                str(e)
            )

    print(
        "GEOCODING FAILED:",
        user.get("name"),
        address
    )

    return None, None


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    lat1 = safe_float(lat1)
    lon1 = safe_float(lon1)
    lat2 = safe_float(lat2)
    lon2 = safe_float(lon2)


    if None in (
        lat1,
        lon1,
        lat2,
        lon2
    ):

        return None


    earth_radius_km = 6371.0


    phi1 =math.radians(
            lat1
        )


    phi2 =math.radians(
            lat2
        )


    delta_phi =math.radians(
            lat2 - lat1
        )


    delta_lambda =math.radians(
            lon2 - lon1
        )


    a = (

        math.sin(
            delta_phi / 2
        ) ** 2

        +

        math.cos(phi1)

        *

        math.cos(phi2)

        *

        math.sin(
            delta_lambda / 2
        ) ** 2

    )


    c =2 * math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a)
        )


    return round(
        earth_radius_km * c,
        2
    )


# ============================================================
# SERIALIZE BUYER
# ============================================================

def serialize_buyer(
    user,
    farmer_lat=None,
    farmer_lon=None
):

    buyer_lat,buyer_lon =geocode_user(
            user
        )


    distance_km =calculate_distance(

            farmer_lat,

            farmer_lon,

            buyer_lat,

            buyer_lon

        )


    return {

        "id":
            str(
                user["_id"]
            ),


        "name":
            user.get(
                "name",
                ""
            ),


        "email":
            user.get(
                "email",
                ""
            ),


        "phone":
            user.get(
                "phone",
                ""
            ),


        "role":
            user.get(
                "role",
                ""
            ),


        "address":
            user.get(
                "address",
                ""
            ),


        "location":
            user.get(
                "location",
                user.get(
                    "address",
                    ""
                )
            ),


        "city": user.get("city") or (
        user.get("address", "").split(",")[-2].strip()
        if len(user.get("address", "").split(",")) >= 2
        else ""
        ),

        "district": user.get("district", ""),

        "state": user.get("state") or (
            user.get("address", "").split(",")[-1].strip()
            if len(user.get("address", "").split(",")) >= 1
            else ""
        ),

        "pincode": user.get("pincode", ""),


        "latitude":
            buyer_lat,


        "longitude":
            buyer_lon,


        "distance_km":
            distance_km,


        "is_verified":
            user.get(
                "is_verified",
                False
            )

    }


# ============================================================
# GET BUYERS
#
# GET /api/buyers
# ============================================================

# ============================================================
# CORS PREFLIGHT
# This route MUST NOT use token_required
# ============================================================

@buyer_bp.route(
    "/api/buyers",
    methods=["OPTIONS"],
    provide_automatic_options=False
)
def buyers_preflight():

    return "", 204


# ============================================================
# GET BUYERS
# Protected route
# ============================================================

@buyer_bp.route(
    "/api/buyers",
    methods=["GET"],
    provide_automatic_options=False
)
@token_required
def get_buyers():

    if request.method == "OPTIONS":

        return "", 200


    try:

        db = get_db()


        # ----------------------------------------------------
        # CURRENT FARMER
        # ----------------------------------------------------

        current_user =get_current_user()


        if not current_user:

            return jsonify({

                "success":
                    False,

                "message":
                    "User not found."

            }), 404


        # ----------------------------------------------------
        # ROLE CHECK
        # ----------------------------------------------------

        current_role =str(
                current_user.get(
                    "role",
                    ""
                )
            ).strip().upper()


        if current_role != "FARMER":

            return jsonify({

                "success":
                    False,

                "message":
                    "Only farmers can access Find Buyers."

            }), 403


        # ----------------------------------------------------
        # FARMER LOCATION
        # ----------------------------------------------------

        farmer_lat,farmer_lon =geocode_user(
                current_user
            )


        print(
            "FARMER LOCATION:",
            farmer_lat,
            farmer_lon
        )


        # ----------------------------------------------------
        # FILTERS
        # ----------------------------------------------------

        buyer_type =request.args.get(
                "type",
                "ALL"
            ).strip().upper()


        search =request.args.get(
                "search",
                ""
            ).strip()


        # ----------------------------------------------------
        # BASE QUERY
        # ----------------------------------------------------

        query = {

            "role": {

                "$in": [

                    "WHOLESALER",

                    "VENDOR"

                ]

            }

        }


        # ----------------------------------------------------
        # TYPE
        # ----------------------------------------------------

        if buyer_type in [

            "WHOLESALER",

            "BULK_BUYER",

            "BULK BUYER"

        ]:

            query["role"] ="WHOLESALER"


        elif buyer_type in [

            "VENDOR",

            "CONSUMER"

        ]:

            query["role"] ="VENDOR"


        # ----------------------------------------------------
        # SEARCH
        # ----------------------------------------------------

        if search:

            query["$or"] = [

                {
                    "name": {
                        "$regex":
                            search,
                        "$options":
                            "i"
                    }
                },

                {
                    "email": {
                        "$regex":
                            search,
                        "$options":
                            "i"
                    }
                },

                {
                    "phone": {
                        "$regex":
                            search,
                        "$options":
                            "i"
                    }
                },

                {
                    "address": {
                        "$regex":
                            search,
                        "$options":
                            "i"
                    }
                },

                {
                    "location": {
                        "$regex":
                            search,
                        "$options":
                            "i"
                    }
                },

                {
                    "city": {
                        "$regex":
                            search,
                        "$options":
                            "i"
                    }
                },

                {
                    "district": {
                        "$regex":
                            search,
                        "$options":
                            "i"
                    }
                },

                {
                    "state": {
                        "$regex":
                            search,
                        "$options":
                            "i"
                    }
                }

            ]


        # ----------------------------------------------------
        # FETCH
        # ----------------------------------------------------

        users =list(

                db["users"]
                .find(query)
                .sort(
                    "name",
                    1
                )

            )


        # ----------------------------------------------------
        # SERIALIZE + DISTANCE
        # ----------------------------------------------------

        buyers = []


        for user in users:

            buyer =serialize_buyer(

                    user,

                    farmer_lat,

                    farmer_lon

                )


            buyers.append(
                buyer
            )


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "success":
                True,

            "count":
                len(buyers),

            "buyers":
                buyers

        }), 200


    except Exception as e:

        print(
            "BUYERS ROUTE ERROR:",
            str(e)
        )


        return jsonify({

            "success":
                False,

            "message":
                "Unable to load buyers.",

            "error":
                str(e)

        }), 500
@buyer_bp.route(
    "/api/buyers/contact",
    methods=["POST"]
)
@token_required
def contact_buyer():

    try:
        db = get_db()
        current_user = get_current_user()

        if not current_user:
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404

        data = request.get_json() or {}

        buyer_id = str(data.get("buyer_id", "")).strip()
        message = str(data.get("message", "")).strip()

        if not buyer_id or not message:
            return jsonify({
                "success": False,
                "message": "Buyer and message are required."
            }), 400

        try:
            buyer = db["users"].find_one({
                "_id": ObjectId(buyer_id)
            })
        except Exception:
            buyer = None

        if not buyer:
            return jsonify({
                "success": False,
                "message": "Buyer not found."
            }), 404

        buyer_email = buyer.get("email", "")

        if not buyer_email:
            return jsonify({
                "success": False,
                "message": "Buyer has no email address."
            }), 400

        farmer_name = current_user.get(
            "name",
            "AgriCentre Farmer"
        )

        subject = "AgriCentre - New Farmer Inquiry"

        body = f"""
Hello {buyer.get("name", "Buyer")},

You have received a new message from a farmer through AgriCentre.

Farmer: {farmer_name}

Message:
{message}

You can contact the farmer through AgriCentre.

Regards,
AgriCentre
"""

        email_sent = send_email(
            buyer_email,
            subject,
            body
        )

        if not email_sent:
            return jsonify({
                "success": False,
                "message": "Unable to send message right now."
            }), 500

        return jsonify({
            "success": True,
            "message": "Message sent successfully to the buyer."
        }), 200

    except Exception as e:

        print(
            "CONTACT BUYER ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Unable to contact buyer.",
            "error": str(e)
        }), 500
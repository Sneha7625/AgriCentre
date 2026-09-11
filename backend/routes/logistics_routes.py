from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from bson import ObjectId

from models.driver_model import DriverModel
from models.delivery_model import DeliveryModel
import json
import urllib.request
import urllib.parse

# ============================================================
# BLUEPRINT
# ============================================================

logistics_bp = Blueprint(
    "logistics",
    __name__,
    url_prefix="/api"
)

# ============================================================
# MODEL HELPERS
# ============================================================

def get_driver_model():
    """
    Create the DriverModel only when a request is being handled.

    This prevents the Flask 'Working outside of application
    context' error during application startup.
    """

    return DriverModel()


def get_delivery_model():
    """
    Create the DeliveryModel only when a request is being handled.
    """

    return DeliveryModel()


def get_db():
    """
    Get the existing MongoDB database connection
    created in app.py.
    """

    return current_app.config["DB"]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def serialize_value(value):
    """
    Convert MongoDB values into JSON-safe values.
    """

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: serialize_value(val)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [
            serialize_value(item)
            for item in value
        ]

    return value


def get_user_id():
    """
    Get the logged-in user's ID from the frontend header.
    """

    return request.headers.get("X-User-Id")


# ============================================================
# ROUTE CALCULATION
# ============================================================

def get_real_routes(pickup, destination):
    """
    Get real road routes between pickup and destination
    using OSRM.
    """

    pickup_lat = float(pickup["latitude"])
    pickup_lng = float(pickup["longitude"])

    destination_lat = float(destination["latitude"])
    destination_lng = float(destination["longitude"])

    # OSRM uses longitude,latitude
    coordinates = (
        f"{pickup_lng},{pickup_lat};"
        f"{destination_lng},{destination_lat}"
    )

    params = urllib.parse.urlencode({
        "alternatives": "true",
        "steps": "true",
        "geometries": "geojson",
        "overview": "full"
    })

    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{coordinates}?{params}"
    )

    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read().decode())

    if data.get("code") != "Ok":
        raise ValueError("Unable to calculate road routes")

    return data.get("routes", [])

def calculate_ai_score(distance_km, eta_hours, cost):
    """
    Multi-factor AI route score.

    Lower score = better route.
    """

    return round(
        (distance_km * 0.35)
        + (eta_hours * 30 * 0.45)
        + (cost / 10 * 0.20),
        2
    )

def build_route_options(routes):
    """
    Convert real OSRM routes into the four
    logistics options shown to the farmer.
    """

    if not routes:
        raise ValueError("No routes found")

    options = []

    for route in routes:

        distance_km = round(
            route["distance"] / 1000,
            2
        )

        eta_hours = round(
            route["duration"] / 3600,
            2
        )

        # Basic transport cost estimate
        estimated_cost = round(
            distance_km * 7.5,
            2
        )

        ai_score = calculate_ai_score(
            distance_km,
            eta_hours,
            estimated_cost
        )

        # -----------------------------------------
        # -----------------------------------------
        # EXTRACT ROUTE STEPS
        # -----------------------------------------

        steps = []

        for leg in route.get(
            "legs",
            []
        ):

            for step in leg.get(
                "steps",
                []
            ):

                name = (
                    step.get("name")
                    or step.get("ref")
                    or ""
                ).strip()

                maneuver =step.get(
                        "maneuver",
                        {}
                    )

                location =maneuver.get(
                        "location"
                    )

                if (
                    name and
                    location and
                    len(location) == 2
                ):

                    steps.append({

                        "name":
                            name,

                        "location":
                            location,

                        "distance_km":
                            round(
                                step.get(
                                    "distance",
                                    0
                                ) / 1000,
                                2
                            )

                    })


        options.append({

            "distance_km":
                distance_km,

            "eta_hours":
                eta_hours,

            "estimated_cost":
                estimated_cost,

            "ai_score":
                ai_score,

            "geometry":
                route["geometry"],

            "steps":
                steps

        })

    # Sort according to different objectives

    fastest = min(
        options,
        key=lambda x: x["eta_hours"]
    )

    shortest = min(
        options,
        key=lambda x: x["distance_km"]
    )

    cheapest = min(
        options,
        key=lambda x: x["estimated_cost"]
    )

    ai_recommended = min(
        options,
        key=lambda x: x["ai_score"]
    )

    return {
        "AI Recommended": ai_recommended,
        "Fastest": fastest,
        "Shortest Distance": shortest,
        "Lowest Cost": cheapest
    }

# ============================================================
# DELIVERY ID GENERATOR
# ============================================================

def generate_delivery_id():
    """
    Generate the next delivery ID.

    Existing format:
        DEL-00032

    Next:
        DEL-00033
    """

    db = get_db()

    latest_delivery = db["deliveries"].find_one(
        {},
        {
            "delivery_id": 1
        },
        sort=[
            ("delivery_id", -1)
        ]
    )

    if not latest_delivery:
        number = 1

    else:
        latest_id = latest_delivery.get(
            "delivery_id",
            "DEL-00000"
        )

        try:
            number = int(
                latest_id.split("-")[1]
            ) + 1

        except (IndexError, ValueError):
            number = (
                db["deliveries"].count_documents({})
                + 1
            )

    return f"DEL-{number:05d}"


# ============================================================
# GET DRIVERS
# ============================================================

@logistics_bp.route(
    "/drivers",
    methods=["GET"]
)
def get_drivers():

    try:
        status = request.args.get("status")

        driver_model = get_driver_model()

        if status:
            drivers = driver_model.get_all_drivers(
                status
            )

        else:
            drivers = driver_model.get_all_drivers()

        drivers = [
            serialize_value(driver)
            for driver in drivers
        ]

        return jsonify({
            "success": True,
            "count": len(drivers),
            "drivers": drivers
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Unable to load drivers",
            "error": str(e)
        }), 500


# ============================================================
# GET SINGLE DRIVER
# ============================================================

@logistics_bp.route(
    "/drivers/<driver_id>",
    methods=["GET"]
)
def get_driver(driver_id):

    try:

        driver_model = get_driver_model()

        driver = driver_model.get_driver_by_id(
            driver_id
        )

        if not driver:

            return jsonify({
                "success": False,
                "message": "Driver not found"
            }), 404

        return jsonify({
            "success": True,
            "driver": serialize_value(driver)
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Unable to load driver",
            "error": str(e)
        }), 500


# ============================================================
# GET DELIVERIES
# ============================================================

@logistics_bp.route(
    "/deliveries",
    methods=["GET"]
)
@logistics_bp.route(
    "/deliveries",
    methods=["GET"]
)
def get_deliveries():

    try:

        delivery_model = get_delivery_model()

        # ----------------------------------------------------
        # GET LOGGED-IN USER FROM JWT
        # ----------------------------------------------------

        user_id = None

        auth_header = request.headers.get(
            "Authorization",
            ""
        )

        if auth_header.startswith("Bearer "):

            token = auth_header.split(
                " ",
                1
            )[1]

            try:

                import jwt

                payload = jwt.decode(
                    token,
                    current_app.config["JWT_SECRET"],
                    algorithms=["HS256"]
                )

                user_id = payload.get(
                    "user_id"
                )

            except Exception:
                user_id = None

        # ----------------------------------------------------
        # FARMER-SPECIFIC DELIVERIES
        # ----------------------------------------------------

        if not user_id:

            return jsonify({
                "success": False,
                "message": "Authentication required"
            }), 401

        deliveries = (
            delivery_model
            .get_deliveries_by_farmer(
                user_id
            )
        )

        deliveries = [
            serialize_value(delivery)
            for delivery in deliveries
        ]

        return jsonify({
            "success": True,
            "count": len(deliveries),
            "deliveries": deliveries
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Unable to load deliveries",
            "error": str(e)
        }), 500


# ============================================================
# GET SINGLE DELIVERY
# ============================================================
# ============================================================
# GET ORDER LOCATIONS
#
# GET /api/logistics/order/<order_id>
#
# Used by the farmer logistics page after an order
# is selected. We do NOT modify the existing orders
# endpoint.
# ============================================================

@logistics_bp.route(
    "/logistics/order/<order_id>",
    methods=["GET"]
)
def get_order_locations(
    order_id
):

    try:

        db = get_db()


        # ----------------------------------------------------
        # FIND ORDER
        # ----------------------------------------------------

        order = db["orders"].find_one({

            "order_id":
                order_id

        })


        if not order:

            return jsonify({

                "success":
                    False,

                "message":
                    "Order not found"

            }), 404


        # ----------------------------------------------------
        # GET FARMER
        # ----------------------------------------------------

        farmer_id =order.get(
                "farmer_id"
            )


        farmer = None


        if farmer_id:

            try:

                if ObjectId.is_valid(
                    str(farmer_id)
                ):

                    farmer =db["users"].find_one({

                            "_id":
                                ObjectId(
                                    str(
                                        farmer_id
                                    )
                                )

                        })

            except Exception:

                farmer = None


        # ----------------------------------------------------
        # GET BUYER
        # ----------------------------------------------------

        buyer_id =order.get(
                "buyer_id"
            )


        buyer = None


        if buyer_id:

            try:

                if ObjectId.is_valid(
                    str(buyer_id)
                ):

                    buyer =db["users"].find_one({

                            "_id":
                                ObjectId(
                                    str(
                                        buyer_id
                                    )
                                )

                        })

            except Exception:

                buyer = None


        # ----------------------------------------------------
        # BUILD PICKUP LOCATION
        # ----------------------------------------------------

        pickup = {

            "address":
                farmer.get(
                    "address",
                    ""
                ) if farmer else "",

            "city":
                farmer.get(
                    "city",
                    ""
                ) if farmer else "",

            "state":
                farmer.get(
                    "state",
                    ""
                ) if farmer else "",

            "latitude":
                farmer.get(
                    "latitude",
                    farmer.get(
                        "lat"
                    )
                ) if farmer else None,

            "longitude":
                farmer.get(
                    "longitude",
                    farmer.get(
                        "lng"
                    )
                ) if farmer else None

        }


        # ----------------------------------------------------
        # BUILD DESTINATION
        # ----------------------------------------------------

        destination = {

            "address":
                buyer.get(
                    "address",
                    ""
                ) if buyer else "",

            "city":
                buyer.get(
                    "city",
                    ""
                ) if buyer else "",

            "state":
                buyer.get(
                    "state",
                    ""
                ) if buyer else "",

            "latitude":
                buyer.get(
                    "latitude",
                    buyer.get(
                        "lat"
                    )
                ) if buyer else None,

            "longitude":
                buyer.get(
                    "longitude",
                    buyer.get(
                        "lng"
                    )
                ) if buyer else None

        }


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "success":
                True,

            "order_id":
                order_id,

            "pickup_location":
                serialize_value(
                    pickup
                ),

            "destination":
                serialize_value(
                    destination
                )

        }), 200


    except Exception as e:

        return jsonify({

            "success":
                False,

            "message":
                "Unable to load order locations",

            "error":
                str(e)

        }), 500
    

@logistics_bp.route(
    "/deliveries/<delivery_id>",
    methods=["GET"]
)
def get_delivery(delivery_id):

    try:

        delivery_model = get_delivery_model()

        delivery = delivery_model.get_delivery_by_id(
            delivery_id
        )

        if not delivery:

            return jsonify({
                "success": False,
                "message": "Delivery not found"
            }), 404

        return jsonify({
            "success": True,
            "delivery": serialize_value(delivery)
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Unable to load delivery",
            "error": str(e)
        }), 500


# ============================================================
# GET ROUTE OPTIONS
# ============================================================

@logistics_bp.route(
    "/routes",
    methods=["POST"]
)

def get_route_options():

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "Request body is required"
            }), 400

        pickup = data.get("pickup")
        destination = data.get("destination")

        if not pickup or not destination:
            return jsonify({
                "success": False,
                "message": (
                    "pickup and destination are required"
                )
            }), 400

        required_coordinates = [
            "latitude",
            "longitude"
        ]

        for location_name, location in [
            ("pickup", pickup),
            ("destination", destination)
        ]:

            for coordinate in required_coordinates:

                if location.get(coordinate) is None:

                    return jsonify({
                        "success": False,
                        "message": (
                            f"{location_name} "
                            f"{coordinate} is required"
                        )
                    }), 400

        routes = get_real_routes(
            pickup,
            destination
        )

        route_options = build_route_options(
            routes
        )

        return jsonify({
            "success": True,
            "recommended": "AI Recommended",
            "routes": route_options
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Unable to calculate routes",
            "error": str(e)
        }), 500
# ============================================================
# CREATE DELIVERY
# ============================================================

@logistics_bp.route(
    "/deliveries",
    methods=["POST"]
)
def create_delivery():

    driver_model = get_driver_model()
    delivery_model = get_delivery_model()

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "Request body is required"
            }), 400

        # ----------------------------------------------------
        # REQUIRED FIELDS
        # ----------------------------------------------------

        required_fields = [
            "order_id",
            "farmer_id",
            "buyer_id",
            "pickup_location",
            "destination",
            "driver_id"
        ]

        missing_fields = [
            field
            for field in required_fields
            if not data.get(field)
        ]

        if missing_fields:

            return jsonify({
                "success": False,
                "message": "Missing required fields",
                "missing_fields": missing_fields
            }), 400

        # ----------------------------------------------------
        # GET DATABASE
        # ----------------------------------------------------

        db = get_db()

        # ----------------------------------------------------
        # CHECK ORDER
        # ----------------------------------------------------

        order = db["orders"].find_one(
            {
                "order_id": data["order_id"]
            }
        )

        if not order:

            return jsonify({
                "success": False,
                "message": "Order not found"
            }), 404

        # ----------------------------------------------------
        # CHECK EXISTING DELIVERY
        # ----------------------------------------------------

        existing_delivery = db["deliveries"].find_one(
            {
                "order_id": data["order_id"]
            }
        )

        if existing_delivery:

            # ----------------------------------------------------
            # UPDATE EXISTING DELIVERY
            # ----------------------------------------------------

            old_driver_id = existing_delivery.get(
                "driver_id"
            )

            new_driver_id = data["driver_id"]

            # If farmer selected a different driver,
            # release the previously assigned driver.
            if (
                old_driver_id and
                old_driver_id != new_driver_id
            ):
                driver_model.release_driver(
                    old_driver_id
                )

            # Check the newly selected driver
            driver = driver_model.get_driver_by_id(
                new_driver_id
            )

            if not driver:

                return jsonify({
                    "success": False,
                    "message": "Driver not found"
                }), 404

            # If the farmer selected a different driver,
            # assign the new one.
            if old_driver_id != new_driver_id:

                assigned = driver_model.assign_driver(
                    new_driver_id
                )

                if not assigned:

                    return jsonify({
                        "success": False,
                        "message": (
                            "Driver is no longer available"
                        )
                    }), 409

            # ----------------------------------------------------
            # VALIDATE ROUTE
            # ----------------------------------------------------

            route_choice = data.get(
                "route_choice",
                "AI Recommended"
            )

            allowed_routes = [
                "AI Recommended",
                "Fastest",
                "Shortest Distance",
                "Lowest Cost"
            ]

            if route_choice not in allowed_routes:

                return jsonify({
                    "success": False,
                    "message": "Invalid route choice",
                    "allowed_routes": allowed_routes
                }), 400

            # ----------------------------------------------------
            # DISTANCE
            # ----------------------------------------------------

            distance_km = data.get(
                "distance_km"
            )

            if distance_km is None:
                distance_km = 100

            distance_km = float(distance_km)

            # ----------------------------------------------------
            # CALCULATE SELECTED ROUTE
            # ----------------------------------------------------

            routes = get_real_routes(
                data["pickup_location"],
                data["destination"]
            )

            route_options = build_route_options(
                routes
            )

            selected_route = route_options[
                route_choice
            ]

            # ----------------------------------------------------
            # UPDATE EXISTING DELIVERY
            # ----------------------------------------------------

            update_data = {

                "driver_id":
                    driver["driver_id"],

                "driver_name":
                    driver["name"],

                "vehicle_number":
                    driver["vehicle_number"],

                "route_choice":
                    route_choice,

                "distance_km":
                    selected_route["distance_km"],

                "estimated_cost":
                    selected_route["estimated_cost"],

                "eta_hours":
                    selected_route["eta_hours"],

                "pickup_location":
                    data["pickup_location"],

                "destination":
                    data["destination"],

                "updated_at":
                    datetime.utcnow()

            }

            db["deliveries"].update_one(
                {
                    "delivery_id":
                        existing_delivery["delivery_id"]
                },
                {
                    "$set": update_data
                }
            )

            updated_delivery = db["deliveries"].find_one(
                {
                    "delivery_id":
                        existing_delivery["delivery_id"]
                },
                {
                    "_id": 0
                }
            )

            return jsonify({
                "success": True,
                "message": (
                    "Logistics plan updated successfully"
                ),
                "delivery":
                    serialize_value(
                        updated_delivery
                    )
            }), 200
        # ----------------------------------------------------
        # GET DRIVER
        # ----------------------------------------------------

        driver = driver_model.get_driver_by_id(
            data["driver_id"]
        )

        if not driver:

            return jsonify({
                "success": False,
                "message": "Driver not found"
            }), 404

        # ----------------------------------------------------
        # ASSIGN DRIVER
        # ----------------------------------------------------

        assigned = driver_model.assign_driver(
            data["driver_id"]
        )

        if not assigned:

            return jsonify({
                "success": False,
                "message": (
                    "Driver is no longer available"
                )
            }), 409

        # ----------------------------------------------------
        # ROUTE CHOICE
        # ----------------------------------------------------

        route_choice = data.get(
            "route_choice",
            "AI Recommended"
        )

        allowed_routes = [
            "AI Recommended",
            "Fastest",
            "Shortest Distance",
            "Lowest Cost"
        ]

        if route_choice not in allowed_routes:

            driver_model.release_driver(
                data["driver_id"]
            )

            return jsonify({
                "success": False,
                "message": "Invalid route choice",
                "allowed_routes": allowed_routes
            }), 400

        # ----------------------------------------------------
        # DISTANCE
        # ----------------------------------------------------

        distance_km = data.get(
            "distance_km"
        )

        if distance_km is None:

            distance_km = 100

        try:

            distance_km = float(
                distance_km
            )

        except (TypeError, ValueError):

            driver_model.release_driver(
                data["driver_id"]
            )

            return jsonify({
                "success": False,
                "message": "distance_km must be a number"
            }), 400

        if distance_km <= 0:

            driver_model.release_driver(
                data["driver_id"]
            )

            return jsonify({
                "success": False,
                "message": (
                    "distance_km must be "
                    "greater than 0"
                )
            }), 400

        # ----------------------------------------------------
        # CALCULATE ROUTES
        # ----------------------------------------------------

        # ----------------------------------------------------
        # CALCULATE REAL ROUTES
        # ----------------------------------------------------

        routes = get_real_routes(
            data["pickup_location"],
            data["destination"]
        )

        route_options = build_route_options(
            routes
        )

        selected_route = route_options[
            route_choice
        ]

        # ----------------------------------------------------
        # GENERATE DELIVERY ID
        # ----------------------------------------------------

        delivery_id = generate_delivery_id()

        scheduled_at = datetime.utcnow()

        # ----------------------------------------------------
        # FARMER ID
        # ----------------------------------------------------

        farmer_id = data["farmer_id"]

        if ObjectId.is_valid(
            str(farmer_id)
        ):

            farmer_id = ObjectId(
                str(farmer_id)
            )

        # ----------------------------------------------------
        # BUYER ID
        # ----------------------------------------------------

        buyer_id = data["buyer_id"]

        if ObjectId.is_valid(
            str(buyer_id)
        ):

            buyer_id = ObjectId(
                str(buyer_id)
            )

        # ----------------------------------------------------
        # DELIVERY DOCUMENT
        # ----------------------------------------------------

        delivery_data = {

            "delivery_id": delivery_id,

            "order_id": data[
                "order_id"
            ],

            "farmer_id": farmer_id,

            "buyer_id": buyer_id,

            "pickup_location": data[
                "pickup_location"
            ],

            "destination": data[
                "destination"
            ],

            "driver_name": driver[
                "name"
            ],

            "vehicle_number": driver[
                "vehicle_number"
            ],

            "distance_km": selected_route[
                "distance_km"
            ],

            "status": "SCHEDULED",

            "estimated_cost": selected_route[
                "estimated_cost"
            ],

            "eta_hours": selected_route[
                "eta_hours"
            ],

            "scheduled_at": scheduled_at,

            # Additional fields for the new
            # logistics functionality.

            "driver_id": driver[
                "driver_id"
            ],

            "route_choice": route_choice
        }

        # ----------------------------------------------------
        # SAVE DELIVERY
        # ----------------------------------------------------

        created_delivery = (
            delivery_model.create_delivery(
                delivery_data
            )
        )

        return jsonify({
            "success": True,
            "message": (
                "Delivery created successfully"
            ),
            "delivery": serialize_value(
                created_delivery
            )
        }), 201

    except ValueError as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400

    except Exception as e:

        return jsonify({
            "success": False,
            "message": (
                "Unable to create delivery"
            ),
            "error": str(e)
        }), 500


# ============================================================
# UPDATE DELIVERY STATUS
# ============================================================

@logistics_bp.route(
    "/deliveries/<delivery_id>/status",
    methods=["PUT"]
)
def update_delivery_status(delivery_id):

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "Request body is required"
            }), 400

        status = data.get(
            "status"
        )

        if not status:

            return jsonify({
                "success": False,
                "message": "status is required"
            }), 400

        status = status.upper()

        delivery_model = get_delivery_model()
        driver_model = get_driver_model()

        delivery = delivery_model.get_delivery_by_id(
            delivery_id
        )

        if not delivery:

            return jsonify({
                "success": False,
                "message": "Delivery not found"
            }), 404

        updated = delivery_model.update_delivery_status(
            delivery_id,
            status
        )

        if not updated:

            return jsonify({
                "success": False,
                "message": (
                    "Unable to update delivery status"
                )
            }), 400

        # ----------------------------------------------------
        # UPDATE DRIVER STATUS
        # ----------------------------------------------------

        driver_id = delivery.get(
            "driver_id"
        )

        if driver_id:

            if status == "DELIVERED":

                driver_model.release_driver(
                    driver_id
                )

            elif status in [
                "PICKED_UP",
                "IN_TRANSIT"
            ]:

                driver_model.update_driver_status(
                    driver_id,
                    "ON_TRIP"
                )

            elif status == "CANCELLED":

                driver_model.release_driver(
                    driver_id
                )

        # ----------------------------------------------------
        # GET UPDATED DELIVERY
        # ----------------------------------------------------

        updated_delivery = (
            delivery_model.get_delivery_by_id(
                delivery_id
            )
        )

        return jsonify({
            "success": True,
            "message": (
                "Delivery status updated"
            ),
            "delivery": serialize_value(
                updated_delivery
            )
        }), 200

    except ValueError as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400

    except Exception as e:

        return jsonify({
            "success": False,
            "message": (
                "Unable to update delivery status"
            ),
            "error": str(e)
        }), 500
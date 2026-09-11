from datetime import datetime, timezone
import math
from urllib.parse import quote_plus

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, request

from routes.auth_routes import token_required
from routes.buyer_routes import geocode_user, calculate_distance


marketplace_bp = Blueprint(
    "marketplace",
    __name__
)


# ============================================================
# DATABASE / USER HELPERS
# ============================================================

def get_db():
    return current_app.config["DB"]


def get_current_user():
    db = get_db()

    try:
        user_id = ObjectId(request.user_id)
    except Exception:
        return None

    return db["users"].find_one({
        "_id": user_id
    })


def role_allowed(user):
    if not user:
        return False

    role = str(
        user.get("role", "")
    ).strip().upper()

    return role in {
        "VENDOR",
        "WHOLESALER",
        "BULK_BUYER",
        "BULK BUYER"
    }


def is_bulk_buyer(user):
    if not user:
        return False

    role = str(
        user.get("role", "")
    ).strip().upper()

    return role in {
        "WHOLESALER",
        "BULK_BUYER",
        "BULK BUYER"
    }


def safe_number(value, default=0):
    try:
        number = float(value)

        if math.isfinite(number):
            return number

    except (
        TypeError,
        ValueError
    ):
        pass

    return default


# ============================================================
# MARKETPLACE ELIGIBILITY
#
# Quality Check is intentionally NOT required right now.
#
# A listing is visible when:
#   - it is not closed/rejected/sold/inactive
#   - available quantity is greater than zero
#
# available_quantity falls back to quantity for older records.
# ============================================================

def marketplace_eligibility_query():
    return {
        "status": {
            "$nin": [
                "CLOSED",
                "REJECTED",
                "SOLD",
                "INACTIVE"
            ]
        },
        "$expr": {
            "$gt": [
                {
                    "$convert": {
                        "input": {
                            "$ifNull": [
                                "$available_quantity",
                                "$quantity"
                            ]
                        },
                        "to": "double",
                        "onError": 0,
                        "onNull": 0
                    }
                },
                0
            ]
        }
    }


# ============================================================
# LOCATION HELPERS
# ============================================================

def get_listing_location(listing):
    location = listing.get(
        "location",
        {}
    )

    if not isinstance(location, dict):
        return {
            "address": str(location or ""),
            "district": "",
            "state": "",
            "pincode": ""
        }

    return location


def location_label(listing):
    location = get_listing_location(
        listing
    )

    district = str(
        location.get(
            "district",
            ""
        ) or ""
    ).strip()

    state = str(
        location.get(
            "state",
            ""
        ) or ""
    ).strip()

    address = str(
        location.get(
            "address",
            ""
        ) or ""
    ).strip()

    if district and state:
        return f"{district}, {state}"

    if district:
        return district

    if state:
        return state

    return address or "Location not specified"


def location_matches(listing, selected):
    if not selected:
        return True

    selected = selected.strip().lower()

    location = get_listing_location(
        listing
    )

    values = {
        str(
            location.get(
                "address",
                ""
            ) or ""
        ).strip().lower(),

        str(
            location.get(
                "district",
                ""
            ) or ""
        ).strip().lower(),

        str(
            location.get(
                "state",
                ""
            ) or ""
        ).strip().lower()
    }

    district = str(
        location.get(
            "district",
            ""
        ) or ""
    ).strip().lower()

    state = str(
        location.get(
            "state",
            ""
        ) or ""
    ).strip().lower()

    if district and state:
        values.add(
            f"{district}, {state}"
        )

    return selected in values


# ============================================================
# FARMER / DISTANCE HELPERS
# ============================================================

def get_farmer(db, farmer_id):
    if not farmer_id:
        return None

    try:
        return db["users"].find_one({
            "_id": ObjectId(farmer_id)
        })
    except Exception:
        return None


def valid_coordinate_pair(latitude, longitude):
    """Return True only for real, usable coordinates."""
    try:
        lat = float(latitude)
        lon = float(longitude)

        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
        ):
            return False

        # 0,0 is normally a placeholder, not a real user location.
        if abs(lat) < 0.000001 and abs(lon) < 0.000001:
            return False

        if not (-90 <= lat <= 90):
            return False

        if not (-180 <= lon <= 180):
            return False

        return True

    except (TypeError, ValueError):
        return False


def geocode_address(address):
    """
    Geocode an address using the same public geocoding approach
    used elsewhere in the project.

    Returns:
        (latitude, longitude)
        or
        (None, None)
    """
    if not address:
        return None, None

    try:
        import requests

        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": str(address),
                "format": "json",
                "limit": 1,
            },
            headers={
                "User-Agent": "AgriCentre/1.0"
            },
            timeout=5,
        )

        if response.status_code != 200:
            return None, None

        results = response.json()

        if not results:
            return None, None

        latitude = safe_number(
            results[0].get("lat"),
            None
        )

        longitude = safe_number(
            results[0].get("lon"),
            None
        )

        if valid_coordinate_pair(
            latitude,
            longitude
        ):
            return latitude, longitude

    except Exception:
        current_app.logger.exception(
            "Marketplace geocoding failed"
        )

    return None, None


def get_user_coordinates(user):
    """
    Resolve a user's coordinates.

    Priority:
        1. latitude/longitude
        2. stored address fields
        3. geocode the stored address
    """
    if not user:
        return None, None

    latitude = user.get(
        "latitude",
        user.get("lat")
    )

    longitude = user.get(
        "longitude",
        user.get("lng")
    )

    if valid_coordinate_pair(
        latitude,
        longitude
    ):
        return float(latitude), float(longitude)

    location = user.get(
        "location",
        {}
    )

    if isinstance(location, dict):
        address_parts = [
            location.get("address"),
            location.get("district"),
            location.get("state"),
            location.get("pincode"),
        ]
    else:
        address_parts = [location]

    address_parts.extend([
        user.get("address"),
        user.get("district"),
        user.get("state"),
        user.get("pincode"),
    ])

    address = ", ".join(
        str(part).strip()
        for part in address_parts
        if part is not None
        and str(part).strip()
    )

    return geocode_address(address)


def get_listing_coordinates(listing):
    """
    Resolve coordinates stored directly on a produce listing.
    """
    latitude = listing.get(
        "latitude",
        listing.get("lat")
    )

    longitude = listing.get(
        "longitude",
        listing.get("lng")
    )

    if valid_coordinate_pair(
        latitude,
        longitude
    ):
        return float(latitude), float(longitude)

    location = get_listing_location(
        listing
    )

    address_parts = [
        location.get("address"),
        location.get("district"),
        location.get("state"),
        location.get("pincode"),
    ]

    address = ", ".join(
        str(part).strip()
        for part in address_parts
        if part is not None
        and str(part).strip()
    )

    return geocode_address(address)


def add_distance_to_listing(
    db,
    listing,
    buyer_lat,
    buyer_lon,
    farmer_cache
):
    farmer_id = listing.get(
        "farmer_id"
    )

    farmer_key = (
        str(farmer_id)
        if farmer_id
        else ""
    )

    # --------------------------------------------------------
    # Resolve farmer coordinates.
    # --------------------------------------------------------

    if farmer_key:
        if farmer_key not in farmer_cache:
            farmer = get_farmer(
                db,
                farmer_key
            )

            farmer_lat = None
            farmer_lon = None

            if farmer:
                farmer_lat, farmer_lon = (
                    get_user_coordinates(
                        farmer
                    )
                )

            # If farmer profile does not have usable
            # coordinates, use the listing location.
            if not valid_coordinate_pair(
                farmer_lat,
                farmer_lon
            ):
                farmer_lat, farmer_lon = (
                    get_listing_coordinates(
                        listing
                    )
                )

            farmer_cache[
                farmer_key
            ] = (
                farmer_lat,
                farmer_lon
            )

    else:
        # No farmer_id: use listing location.
        farmer_lat, farmer_lon = (
            get_listing_coordinates(
                listing
            )
        )

    if not farmer_key:
        coordinates = (
            farmer_lat,
            farmer_lon
        )
    else:
        coordinates = farmer_cache[
            farmer_key
        ]

    farmer_lat, farmer_lon = coordinates

    if not valid_coordinate_pair(
        buyer_lat,
        buyer_lon
    ):
        return None

    if not valid_coordinate_pair(
        farmer_lat,
        farmer_lon
    ):
        return None

    return calculate_distance(
        farmer_lat,
        farmer_lon,
        buyer_lat,
        buyer_lon
    )


# ============================================================
# SERIALIZATION
# ============================================================

def serialize_listing(
    db,
    listing,
    distance_km=None
):
    location = get_listing_location(
        listing
    )

    farmer_id = listing.get(
        "farmer_id"
    )

    farmer = get_farmer(
        db,
        farmer_id
    )

    farmer_name = (
        listing.get(
            "farmer_name"
        )
        or (
            farmer.get("name")
            if farmer
            else ""
        )
        or "AgriCentre Farmer"
    )

    available_quantity = listing.get(
        "available_quantity",
        listing.get(
            "quantity",
            0
        )
    )

    price_per_unit = listing.get(
        "price_per_unit",
        listing.get(
            "price",
            0
        )
    )

    result = {
        "id": str(
            listing["_id"]
        ),

        "listing_id": listing.get(
            "listing_id",
            ""
        ),

        "farmer_id": (
            str(farmer_id)
            if farmer_id
            else ""
        ),

        "farmer_name": farmer_name,

        "farmer_email": (
            farmer.get(
                "email",
                ""
            )
            if farmer
            else ""
        ),

        "produce_name": listing.get(
            "produce_name",
            ""
        ),

        "category": listing.get(
            "category",
            ""
        ),

        "description": listing.get(
            "description",
            ""
        ),

        "quantity": listing.get(
            "quantity",
            0
        ),

        "available_quantity": available_quantity,

        "unit": listing.get(
            "unit",
            "KG"
        ),

        "minimum_order_quantity": listing.get(
            "minimum_order_quantity",
            listing.get(
                "minimum_order",
                0
            )
        ),

        "price_per_unit": price_per_unit,

        "price_type": listing.get(
            "price_type",
            "FIXED"
        ),

        "location": location.get(
            "address",
            ""
        ),

        "district": location.get(
            "district",
            ""
        ),

        "state": location.get(
            "state",
            ""
        ),

        "pincode": location.get(
            "pincode",
            ""
        ),

        "location_label": location_label(
            listing
        ),

        "quality_status": listing.get(
            "quality_status",
            "PENDING"
        ),

        "status": listing.get(
            "status",
            "PENDING"
        ),

        "image_url": listing.get(
            "image_url",
            ""
        ),

        "harvest_date": (
            listing["harvest_date"].isoformat()
            if hasattr(
                listing.get("harvest_date"),
                "isoformat"
            )
            else listing.get(
                "harvest_date"
            )
        ),

        "available_from": (
            listing["available_from"].isoformat()
            if hasattr(
                listing.get("available_from"),
                "isoformat"
            )
            else listing.get(
                "available_from"
            )
        ),

        "distance_km": distance_km
    }

    return result


# ============================================================
# GET MARKETPLACE
# GET /api/marketplace
# ============================================================

@marketplace_bp.route(
    "/api/marketplace",
    methods=["GET"]
)
@token_required
def browse_marketplace():
    db = get_db()
    user = get_current_user()

    if not role_allowed(user):
        return jsonify({
            "success": False,
            "message": (
                "Marketplace is available only "
                "to Buyer and Bulk Buyer accounts."
            )
        }), 403

    search = request.args.get(
        "search",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    location_filter = request.args.get(
        "location",
        ""
    ).strip()

    farmer_id = request.args.get(
        "farmer_id",
        ""
    ).strip()

    min_price = request.args.get(
        "min_price",
        ""
    ).strip()

    max_price = request.args.get(
        "max_price",
        ""
    ).strip()

    min_quantity = request.args.get(
        "min_quantity",
        ""
    ).strip()

    sort = request.args.get(
        "sort",
        "newest"
    ).strip().lower()

    # --------------------------------------------------------
    # Base MongoDB query
    # --------------------------------------------------------

    base_query = marketplace_eligibility_query()

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    if search:
        base_query["$or"] = [
            {
                "produce_name": {
                    "$regex": search,
                    "$options": "i"
                }
            },
            {
                "category": {
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
                "location.address": {
                    "$regex": search,
                    "$options": "i"
                }
            },
            {
                "location.district": {
                    "$regex": search,
                    "$options": "i"
                }
            },
            {
                "location.state": {
                    "$regex": search,
                    "$options": "i"
                }
            }
        ]

    # --------------------------------------------------------
    # Category
    # --------------------------------------------------------

    if (
        category
        and category.upper() != "ALL"
    ):
        base_query["category"] = {
            "$regex": (
                f"^{category}$"
            ),
            "$options": "i"
        }

    # --------------------------------------------------------
    # Farmer
    # --------------------------------------------------------

    if farmer_id:
        try:
            base_query["farmer_id"] = ObjectId(
                farmer_id
            )
        except Exception:
            return jsonify({
                "success": False,
                "message": "Invalid farmer ID."
            }), 400

    # --------------------------------------------------------
    # Numeric filters
    #
    # Use $expr + $convert so the filter works with both
    # current numeric records and older records.
    # --------------------------------------------------------

    numeric_conditions = []

    if min_price:
        try:
            numeric_conditions.append({
                "$gte": [
                    {
                        "$convert": {
                            "input": {
                                "$ifNull": [
                                    "$price_per_unit",
                                    "$price"
                                ]
                            },
                            "to": "double",
                            "onError": 0,
                            "onNull": 0
                        }
                    },
                    float(min_price)
                ]
            })
        except ValueError:
            return jsonify({
                "success": False,
                "message": (
                    "Minimum price must be "
                    "a valid number."
                )
            }), 400

    if max_price:
        try:
            numeric_conditions.append({
                "$lte": [
                    {
                        "$convert": {
                            "input": {
                                "$ifNull": [
                                    "$price_per_unit",
                                    "$price"
                                ]
                            },
                            "to": "double",
                            "onError": 0,
                            "onNull": 0
                        }
                    },
                    float(max_price)
                ]
            })
        except ValueError:
            return jsonify({
                "success": False,
                "message": (
                    "Maximum price must be "
                    "a valid number."
                )
            }), 400

    # --------------------------------------------------------
    # Bulk Buyer quantity rule
    #
    # Normal Buyer:
    #   > 0 KG
    #
    # Bulk Buyer:
    #   100 KG minimum by default
    #   OR the user-selected minimum quantity.
    # --------------------------------------------------------

    if min_quantity:
        try:
            required_quantity = float(
                min_quantity
            )
        except ValueError:
            return jsonify({
                "success": False,
                "message": (
                    "Minimum quantity must be "
                    "a valid number."
                )
            }), 400
    elif is_bulk_buyer(user):
        required_quantity = 100
    else:
        required_quantity = None

    if required_quantity is not None:
        numeric_conditions.append({
            "$gte": [
                {
                    "$convert": {
                        "input": {
                            "$ifNull": [
                                "$available_quantity",
                                "$quantity"
                            ]
                        },
                        "to": "double",
                        "onError": 0,
                        "onNull": 0
                    }
                },
                required_quantity
            ]
        })

    if numeric_conditions:
        base_query["$expr"] = {
            "$and": numeric_conditions
        }

    # --------------------------------------------------------
    # Fetch all eligible listings first.
    #
    # This is important because filter options must NOT shrink
    # just because the user searched for something.
    # --------------------------------------------------------

    try:
        all_eligible = list(
            db["produce"].find(
                marketplace_eligibility_query()
            )
        )

        raw_listings = list(
            db["produce"].find(
                base_query
            )
        )

    except Exception as exc:
        current_app.logger.exception(
            "Marketplace database error"
        )

        return jsonify({
            "success": False,
            "message": (
                "Unable to load marketplace."
            ),
            "error": str(exc)
        }), 500

    # --------------------------------------------------------
    # Location filter is handled after MongoDB because the UI
    # value may represent district + state.
    # --------------------------------------------------------

    if location_filter:
        raw_listings = [
            listing
            for listing in raw_listings
            if location_matches(
                listing,
                location_filter
            )
        ]

    # --------------------------------------------------------
    # Buyer coordinates are only needed for nearest sorting.
    # --------------------------------------------------------

    buyer_lat = None
    buyer_lon = None
    farmer_cache = {}

    if sort == "nearest":
        buyer_lat, buyer_lon = get_user_coordinates(
            user
        )

    # --------------------------------------------------------
    # Serialize
    # --------------------------------------------------------

    listings = []

    for listing in raw_listings:
        distance_km = None

        if (
            sort == "nearest"
            and buyer_lat is not None
            and buyer_lon is not None
        ):
            distance_km = add_distance_to_listing(
                db,
                listing,
                buyer_lat,
                buyer_lon,
                farmer_cache
            )

        listings.append(
            serialize_listing(
                db,
                listing,
                distance_km
            )
        )

    # --------------------------------------------------------
    # Sorting
    # --------------------------------------------------------

    if sort == "price_low":
        listings.sort(
            key=lambda item: safe_number(
                item.get("price_per_unit"),
                float("inf")
            )
        )

    elif sort == "price_high":
        listings.sort(
            key=lambda item: safe_number(
                item.get("price_per_unit"),
                -float("inf")
            ),
            reverse=True
        )

    elif sort == "quantity":
        listings.sort(
            key=lambda item: safe_number(
                item.get("available_quantity"),
                0
            ),
            reverse=True
        )

    elif sort == "nearest":
        listings.sort(
            key=lambda item: (
                item.get("distance_km")
                if item.get("distance_km")
                is not None
                else float("inf")
            )
        )

    else:
        # Newest: some existing listing documents may not have
        # created_at, so never compare None with datetime values.
        def newest_timestamp(item):
            for raw in raw_listings:
                if str(raw.get("_id")) == item["id"]:
                    value = raw.get("created_at")

                    if hasattr(value, "timestamp"):
                        return value.timestamp()

                    return 0

            return 0

        listings.sort(
            key=newest_timestamp,
            reverse=True
        )

    # --------------------------------------------------------
    # Dynamic filter options
    #
    # These come from ALL eligible listings, NOT from the
    # current filtered result. Therefore:
    #
    # Search = Tomato
    # does NOT make the crop dropdown contain only Tomato.
    # --------------------------------------------------------

    categories = sorted({
        str(
            listing.get(
                "category",
                ""
            )
        ).strip()
        for listing in all_eligible
        if str(
            listing.get(
                "category",
                ""
            )
        ).strip()
    })

    location_map = {}

    for listing in all_eligible:
        label = location_label(
            listing
        )

        if label == "Location not specified":
            continue

        location_map[label.lower()] = label

    locations = [
        {
            "value": label,
            "label": label
        }
        for label in sorted(
            location_map.values(),
            key=lambda value: value.lower()
        )
    ]

    return jsonify({
        "success": True,
        "count": len(listings),
        "listings": listings,
        "nearest_location_available": (
            valid_coordinate_pair(
                buyer_lat,
                buyer_lon
            )
            if sort == "nearest"
            else None
        ),
        "filters": {
            "categories": categories,
            "locations": locations
        },
        "bulk_rule": {
            "is_bulk_buyer": is_bulk_buyer(user),
            "default_min_quantity": (
                100
                if is_bulk_buyer(user)
                else 0
            )
        }
    }), 200


# ============================================================
# SINGLE LISTING
# GET /api/marketplace/listing/<listing_id>
# ============================================================

@marketplace_bp.route(
    "/api/marketplace/listing/<listing_id>",
    methods=["GET"]
)
@token_required
def marketplace_listing(listing_id):
    db = get_db()
    user = get_current_user()

    if not role_allowed(user):
        return jsonify({
            "success": False,
            "message": "Buyer access required."
        }), 403

    try:
        object_id = ObjectId(
            listing_id
        )
    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid listing ID."
        }), 400

    query = marketplace_eligibility_query()
    query["_id"] = object_id

    listing = db["produce"].find_one(
        query
    )

    if not listing:
        return jsonify({
            "success": False,
            "message": (
                "Listing not found or no longer "
                "available."
            )
        }), 404

    return jsonify({
        "success": True,
        "listing": serialize_listing(
            db,
            listing
        )
    }), 200


# ============================================================
# FIND FARMERS
# GET /api/marketplace/farmers
# ============================================================

@marketplace_bp.route(
    "/api/marketplace/farmers",
    methods=["GET"]
)
@token_required
def marketplace_farmers():
    db = get_db()
    user = get_current_user()

    if not role_allowed(user):
        return jsonify({
            "success": False,
            "message": "Buyer access required."
        }), 403

    search = request.args.get(
        "search",
        ""
    ).strip()

    try:
        listings = list(
            db["produce"].find(
                marketplace_eligibility_query()
            )
        )
    except Exception as exc:
        current_app.logger.exception(
            "Marketplace farmers error"
        )

        return jsonify({
            "success": False,
            "message": "Unable to load farmers.",
            "error": str(exc)
        }), 500

    if search:
        search_lower = search.lower()

        listings = [
            listing
            for listing in listings
            if search_lower in " ".join([
                str(
                    listing.get(
                        "farmer_name",
                        ""
                    )
                ),
                str(
                    listing.get(
                        "produce_name",
                        ""
                    )
                ),
                location_label(
                    listing
                )
            ]).lower()
        ]

    # Bulk buyers only see farmers with at least 100 KG
    # available on one of their listings.
    if is_bulk_buyer(user):
        listings = [
            listing
            for listing in listings
            if safe_number(
                listing.get(
                    "available_quantity",
                    listing.get(
                        "quantity",
                        0
                    )
                )
            ) >= 100
        ]

    farmers = {}

    for listing in listings:
        farmer_id = listing.get(
            "farmer_id"
        )

        if not farmer_id:
            continue

        key = str(
            farmer_id
        )

        if key not in farmers:
            farmers[key] = {
                "farmer_id": key,
                "farmer_name": listing.get(
                    "farmer_name",
                    "Farmer"
                ),
                "location": location_label(
                    listing
                ),
                "district": get_listing_location(
                    listing
                ).get(
                    "district",
                    ""
                ),
                "state": get_listing_location(
                    listing
                ).get(
                    "state",
                    ""
                ),
                "listing_count": 0,
                "produce": []
            }

        farmers[key][
            "listing_count"
        ] += 1

        farmers[key][
            "produce"
        ].append({
            "listing_id": listing.get(
                "listing_id",
                ""
            ),
            "produce_name": listing.get(
                "produce_name",
                ""
            ),
            "available_quantity": listing.get(
                "available_quantity",
                listing.get(
                    "quantity",
                    0
                )
            ),
            "unit": listing.get(
                "unit",
                "KG"
            ),
            "price_per_unit": listing.get(
                "price_per_unit",
                listing.get(
                    "price",
                    0
                )
            )
        })

    result = sorted(
        farmers.values(),
        key=lambda farmer: str(
            farmer.get(
                "farmer_name",
                ""
            )
        ).lower()
    )

    return jsonify({
        "success": True,
        "count": len(result),
        "farmers": result
    }), 200

# ============================================================
# FAVORITES
# ============================================================

@marketplace_bp.route(
    "/api/marketplace/favorites",
    methods=["GET"]
)
@token_required
def get_favorites():
    db = get_db()
    user = get_current_user()

    if not role_allowed(user):
        return jsonify({
            "success": False,
            "message": "Buyer access required."
        }), 403

    favorite_ids = user.get(
        "favorite_listing_ids",
        []
    )

    if not isinstance(favorite_ids, list):
        favorite_ids = []

    object_ids = []

    for value in favorite_ids:
        try:
            object_ids.append(ObjectId(str(value)))
        except Exception:
            continue

    if not object_ids:
        return jsonify({
            "success": True,
            "count": 0,
            "items": [],
            "listings": []
        }), 200

    query = marketplace_eligibility_query()
    query["_id"] = {
        "$in": object_ids
    }

    listings = list(
        db["produce"].find(query)
    )

    items = [
        serialize_listing(
            db,
            listing
        )
        for listing in listings
    ]

    # Keep only valid listing IDs in the user's favorites.
    valid_ids = [
        str(listing["_id"])
        for listing in listings
    ]

    if valid_ids != [
        str(value)
        for value in favorite_ids
    ]:
        db["users"].update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "favorite_listing_ids": valid_ids
                }
            }
        )

    return jsonify({
        "success": True,
        "count": len(items),

        # "items" is what favorites.html uses.
        "items": items,

        # Keep "listings" for compatibility.
        "listings": items

    }), 200


@marketplace_bp.route(
    "/api/marketplace/favorites",
    methods=["POST"]
)
@token_required
def add_favorite():
    db = get_db()
    user = get_current_user()

    if not role_allowed(user):
        return jsonify({
            "success": False,
            "message": "Buyer access required."
        }), 403

    data = request.get_json() or {}

    listing_id = str(
        data.get(
            "listing_id",
            ""
        )
    ).strip()

    if not listing_id:
        return jsonify({
            "success": False,
            "message": "Listing ID is required."
        }), 400

    try:
        object_id = ObjectId(listing_id)
    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid listing ID."
        }), 400

    query = marketplace_eligibility_query()
    query["_id"] = object_id

    listing = db["produce"].find_one(query)

    if not listing:
        return jsonify({
            "success": False,
            "message": (
                "Listing not found or no longer available."
            )
        }), 404

    favorite_ids = user.get(
        "favorite_listing_ids",
        []
    )

    if not isinstance(favorite_ids, list):
        favorite_ids = []

    favorite_ids = [
        str(value)
        for value in favorite_ids
    ]

    if listing_id in favorite_ids:
        return jsonify({
            "success": True,
            "already_favorite": True,
            "message": "Already in favorites."
        }), 200

    favorite_ids.append(listing_id)

    db["users"].update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "favorite_listing_ids": favorite_ids,
                "updated_at": datetime.now(
                    timezone.utc
                )
            }
        }
    )

    return jsonify({
        "success": True,
        "already_favorite": False,
        "message": "Added to favorites.",
        "listing_id": listing_id
    }), 200


@marketplace_bp.route(
    "/api/marketplace/favorites/<listing_id>",
    methods=["DELETE"]
)
@token_required
def remove_favorite(listing_id):
    db = get_db()
    user = get_current_user()

    if not role_allowed(user):
        return jsonify({
            "success": False,
            "message": "Buyer access required."
        }), 403

    target_id = str(
        listing_id
    ).strip()

    favorite_ids = user.get(
        "favorite_listing_ids",
        []
    )

    if not isinstance(favorite_ids, list):
        favorite_ids = []

    new_favorites = [
        str(value)
        for value in favorite_ids
        if str(value) != target_id
    ]

    removed = len(new_favorites) != len(favorite_ids)

    db["users"].update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "favorite_listing_ids": new_favorites,
                "updated_at": datetime.now(
                    timezone.utc
                )
            }
        }
    )

    return jsonify({
        "success": True,
        "removed": removed,
        "message": (
            "Removed from favorites."
            if removed
            else "Item was not in favorites."
        )
    }), 200
# ============================================================
# CART
# ============================================================

BULK_BUYER_ROLES = {
    "WHOLESALER",
    "BULK_BUYER",
    "BULK BUYER"
}


def cart_minimum_quantity(user, listing):

    role = str(
        user.get("role", "")
    ).strip().upper()

    try:
        listing_moq = float(
            listing.get(
                "minimum_order_quantity",
                listing.get("minimum_order", 1)
            ) or 1
        )
    except (TypeError, ValueError):
        listing_moq = 1

    if role in BULK_BUYER_ROLES:
        return max(listing_moq, 100)

    return max(listing_moq, 1)


def find_cart_listing(db, listing_id):
    try:
        object_id = ObjectId(str(listing_id).strip())
    except Exception:
        return None

    return db["produce"].find_one({
        "_id": object_id,

        "status": {
            "$nin": [
                "CLOSED",
                "REJECTED",
                "SOLD",
                "INACTIVE"
            ]
        },

        "$expr": {
            "$gt": [
                {
                    "$convert": {
                        "input": {
                            "$ifNull": [
                                "$available_quantity",
                                "$quantity"
                            ]
                        },
                        "to": "double",
                        "onError": 0,
                        "onNull": 0
                    }
                },
                0
            ]
        }
    })

# ============================================================
# GET CART
# ============================================================

@marketplace_bp.route(
    "/api/marketplace/cart",
    methods=["GET"]
)
@token_required
def get_cart():

    db = get_db()
    user = get_current_user()

    if not role_allowed(user):

        return jsonify({
            "success": False,
            "message": "Buyer access required."
        }), 403

    cart = user.get(
        "cart_items",
        []
    )

    if not isinstance(cart, list):
        cart = []

    result = []

    for item in cart:

        listing_id = str(
            item.get(
                "listing_id",
                ""
            )
        ).strip()

        if not listing_id:
            continue

        listing = find_cart_listing(
            db,
            listing_id
        )

        if not listing:
            continue

        data = serialize_listing(
            db,
            listing
        )

        # ----------------------------------------------------
        # THIS IS THE IMPORTANT FIX
        # Frontend expects "quantity" to mean CART quantity.
        # ----------------------------------------------------

        try:
            cart_quantity = float(
                item.get(
                    "quantity",
                    0
                )
            )
        except (TypeError, ValueError):
            cart_quantity = 0

        data["quantity"] = cart_quantity
        data["cart_quantity"] = cart_quantity

        data["cart_minimum_quantity"] = (
            cart_minimum_quantity(
                user,
                listing
            )
        )

        try:
            price = float(
                listing.get(
                    "price_per_unit",
                    listing.get(
                        "price",
                        0
                    )
                ) or 0
            )
        except (TypeError, ValueError):
            price = 0

        data["estimated_total"] = (
            cart_quantity * price
        )

        result.append(data)

    return jsonify({

        "success": True,

        "role": str(
            user.get(
                "role",
                ""
            )
        ).strip().upper(),

        "cart_type": (
            "BULK"
            if str(
                user.get(
                    "role",
                    ""
                )
            ).strip().upper()
            in BULK_BUYER_ROLES
            else "NORMAL"
        ),

        "count": len(result),

        "items": result

    }), 200


# ============================================================
# ADD / UPDATE CART
# ============================================================

@marketplace_bp.route(
    "/api/marketplace/cart",
    methods=["POST"]
)
@token_required
def add_cart():

    db = get_db()
    user = get_current_user()

    if not role_allowed(user):

        return jsonify({
            "success": False,
            "message": "Buyer access required."
        }), 403

    data = request.get_json() or {}

    listing_id = str(
        data.get(
            "listing_id",
            ""
        )
    ).strip()

    if not listing_id:

        return jsonify({
            "success": False,
            "message": "Listing ID is required."
        }), 400

    try:

        quantity = float(
            data.get(
                "quantity",
                0
            )
        )

    except (TypeError, ValueError):

        quantity = 0

    if quantity <= 0:

        return jsonify({
            "success": False,
            "message": "Quantity must be greater than zero."
        }), 400

    listing = find_cart_listing(
        db,
        listing_id
    )

    if not listing:

        return jsonify({
            "success": False,
            "message": (
                "Listing not found or no longer available."
            )
        }), 404

    try:

        available = float(
            listing.get(
                "available_quantity",
                listing.get(
                    "quantity",
                    0
                )
            ) or 0
        )

    except (TypeError, ValueError):

        available = 0

    minimum = cart_minimum_quantity(
        user,
        listing
    )

    unit = listing.get(
        "unit",
        "KG"
    )

    # --------------------------------------------------------
    # MOQ
    # --------------------------------------------------------

    if quantity < minimum:

        return jsonify({

            "success": False,

            "message": (
                f"Minimum quantity is "
                f"{minimum:g} {unit}."
            ),

            "minimum_quantity": minimum

        }), 400

    # --------------------------------------------------------
    # STOCK
    # --------------------------------------------------------

    if quantity > available:

        return jsonify({

            "success": False,

            "message": (
                f"Only {available:g} "
                f"{unit} is available."
            ),

            "available_quantity": available

        }), 400

    # --------------------------------------------------------
    # EXISTING CART
    # --------------------------------------------------------

    cart = user.get(
        "cart_items",
        []
    )

    if not isinstance(cart, list):
        cart = []

    updated = False

    for item in cart:

        if str(
            item.get(
                "listing_id",
                ""
            )
        ) == listing_id:

            item["quantity"] = quantity

            updated = True

            break

    # --------------------------------------------------------
    # NEW ITEM
    # --------------------------------------------------------

    if not updated:

        cart.append({

            "listing_id":
                listing_id,

            "quantity":
                quantity

        })

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    db["users"].update_one(

        {
            "_id":
                user["_id"]
        },

        {
            "$set": {

                "cart_items":
                    cart,

                "updated_at":
                    datetime.now(
                        timezone.utc
                    )

            }
        }

    )

    return jsonify({

        "success": True,

        "message":
            "Added to cart.",

        "listing_id":
            listing_id,

        "quantity":
            quantity,

        "minimum_quantity":
            minimum,

        "available_quantity":
            available,

        "cart_items":
            cart

    }), 200


# ============================================================
# REMOVE CART ITEM
# ============================================================
# ============================================================
# REMOVE CART ITEM
# ============================================================

@marketplace_bp.route(
    "/api/marketplace/cart/<listing_id>",
    methods=["DELETE"]
)
@token_required
def remove_cart(listing_id):

    db = get_db()
    user = get_current_user()

    if not role_allowed(user):
        return jsonify({
            "success": False,
            "message": "Buyer access required."
        }), 403

    target_id = str(
        listing_id
    ).strip()

    cart = user.get(
        "cart_items",
        []
    )

    if not isinstance(cart, list):
        cart = []

    new_cart = []
    removed = False

    for item in cart:

        stored_id = str(
            item.get(
                "listing_id",
                ""
            )
        ).strip()

        if stored_id == target_id:
            removed = True
            continue

        new_cart.append(item)

    # --------------------------------------------------------
    # SAVE THE NEW CART DIRECTLY
    # --------------------------------------------------------

    db["users"].update_one(
        {
            "_id": user["_id"]
        },
        {
            "$set": {
                "cart_items": new_cart,
                "updated_at": datetime.now(
                    timezone.utc
                )
            }
        }
    )

    # --------------------------------------------------------
    # VERIFY FROM DATABASE
    # --------------------------------------------------------

    check_user = db["users"].find_one(
        {
            "_id": user["_id"]
        },
        {
            "cart_items": 1
        }
    )

    check_cart = (
        check_user.get(
            "cart_items",
            []
        )
        if check_user
        else []
    )

    return jsonify({
        "success": True,
        "removed": removed,
        "remaining_items": len(check_cart),
        "message": (
            "Item removed from cart."
            if removed
            else "Item was not found in cart."
        )
    }), 200
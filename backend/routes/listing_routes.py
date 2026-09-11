from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from pathlib import Path
from bson import ObjectId
from werkzeug.utils import secure_filename
import uuid
import os

from routes.auth_routes import token_required


listing_bp = Blueprint("listing", __name__)


# ============================================================
# CONFIGURATION
# ============================================================

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


# ============================================================
# HELPERS
# ============================================================

def get_db():
    return current_app.config["DB"]


def allowed_image(filename):
    """
    Check whether the uploaded file has an allowed image extension.
    """

    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


def get_current_farmer():
    """
    Get the currently authenticated farmer.

    The farmer ID comes from the JWT.
    We NEVER trust farmer_id sent by the frontend.
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


def generate_listing_id():
    """
    Generate a unique listing ID.

    Example:
    LIST-7F3A91C2
    """

    return "LIST-" + uuid.uuid4().hex[:8].upper()


# ============================================================
# CREATE PRODUCE LISTING
# POST /api/listings
# ============================================================

@listing_bp.route("/api/listings", methods=["POST"])
@token_required
def create_listing():

    db = get_db()


    # ========================================================
    # 1. VERIFY FARMER
    # ========================================================

    farmer = get_current_farmer()

    if not farmer:

        return jsonify({
            "success": False,
            "message": "Only Farmer accounts can create produce listings."
        }), 403


    # ========================================================
    # 2. READ FORM DATA
    # ========================================================

    produce_name = request.form.get(
        "produce_name",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    ).strip().upper()

    description = request.form.get(
        "description",
        ""
    ).strip()

    quantity_raw = request.form.get(
        "quantity",
        ""
    ).strip()

    unit = request.form.get(
        "unit",
        ""
    ).strip().upper()

    minimum_order_raw = request.form.get(
        "minimum_order_quantity",
        ""
    ).strip()

    price_raw = request.form.get(
        "price_per_unit",
        ""
    ).strip()

    price_type = request.form.get(
        "price_type",
        "FIXED"
    ).strip().upper()

    location = request.form.get(
        "location",
        ""
    ).strip()

    district = request.form.get(
        "district",
        ""
    ).strip()

    state = request.form.get(
        "state",
        ""
    ).strip()

    pincode = request.form.get(
        "pincode",
        ""
    ).strip()

    # IMPORTANT:
    # Final HTML uses pickup_details.
    pickup_instructions = request.form.get(
        "pickup_details",
        ""
    ).strip()

    harvest_date_raw = request.form.get(
        "harvest_date",
        ""
    ).strip()

    available_from_raw = request.form.get(
        "available_from",
        ""
    ).strip()

    available_until_raw = request.form.get(
        "available_until",
        ""
    ).strip()


    # ========================================================
    # 3. REQUIRED FIELD VALIDATION
    # ========================================================

    required_fields = {
        "produce_name": produce_name,
        "category": category,
        "quantity": quantity_raw,
        "unit": unit,
        "minimum_order_quantity": minimum_order_raw,
        "price_per_unit": price_raw,
        "location": location,
        "district": district,
        "state": state,
        "pincode": pincode,
        "harvest_date": harvest_date_raw,
        "available_from": available_from_raw
    }

    for field, value in required_fields.items():

        if not value:

            return jsonify({
                "success": False,
                "message": f"{field} is required."
            }), 400


    # ========================================================
    # 4. NUMERIC VALIDATION
    # ========================================================

    try:

        quantity = float(
            quantity_raw
        )

    except ValueError:

        return jsonify({
            "success": False,
            "message": "Quantity must be a valid number."
        }), 400


    try:

        minimum_order_quantity = float(
            minimum_order_raw
        )

    except ValueError:

        return jsonify({
            "success": False,
            "message": "Minimum order quantity must be a valid number."
        }), 400


    try:

        price_per_unit = float(
            price_raw
        )

    except ValueError:

        return jsonify({
            "success": False,
            "message": "Price must be a valid number."
        }), 400


    if quantity <= 0:

        return jsonify({
            "success": False,
            "message": "Quantity must be greater than zero."
        }), 400


    if minimum_order_quantity <= 0:

        return jsonify({
            "success": False,
            "message": "Minimum order quantity must be greater than zero."
        }), 400


    if minimum_order_quantity > quantity:

        return jsonify({
            "success": False,
            "message": (
                "Minimum order quantity cannot exceed "
                "available quantity."
            )
        }), 400


    if price_per_unit <= 0:

        return jsonify({
            "success": False,
            "message": "Price must be greater than zero."
        }), 400


    # ========================================================
    # 5. PINCODE VALIDATION
    # ========================================================

    if (
        len(pincode) != 6
        or not pincode.isdigit()
    ):

        return jsonify({
            "success": False,
            "message": "Pincode must be a valid 6-digit number."
        }), 400


    # ========================================================
    # 6. IMAGE VALIDATION
    # ========================================================

    image = request.files.get("image")

    if not image:

        return jsonify({
            "success": False,
            "message": "Produce image is required."
        }), 400


    if not image.filename:

        return jsonify({
            "success": False,
            "message": "Please select an image."
        }), 400


    if not allowed_image(image.filename):

        return jsonify({
            "success": False,
            "message": (
                "Only JPG, JPEG, PNG and WEBP images "
                "are allowed."
            )
        }), 400


    # ========================================================
    # 7. IMAGE SIZE VALIDATION
    # ========================================================

    image.seek(
        0,
        os.SEEK_END
    )

    image_size = image.tell()

    image.seek(0)


    if image_size > MAX_IMAGE_SIZE:

        return jsonify({
            "success": False,
            "message": "Image size must not exceed 5 MB."
        }), 400


    # ========================================================
    # 8. PARSE DATES BEFORE SAVING IMAGE
    # ========================================================

    try:

        harvest_date = datetime.strptime(
            harvest_date_raw,
            "%Y-%m-%d"
        ).replace(
            tzinfo=timezone.utc
        )

    except ValueError:

        return jsonify({
            "success": False,
            "message": "Invalid harvest date."
        }), 400


    try:

        available_from = datetime.strptime(
            available_from_raw,
            "%Y-%m-%d"
        ).replace(
            tzinfo=timezone.utc
        )

    except ValueError:

        return jsonify({
            "success": False,
            "message": "Invalid availability date."
        }), 400


    available_until = None

    if available_until_raw:

        try:

            available_until = datetime.strptime(
                available_until_raw,
                "%Y-%m-%d"
            ).replace(
                tzinfo=timezone.utc
            )

        except ValueError:

            return jsonify({
                "success": False,
                "message": "Invalid available-until date."
            }), 400


        if available_until < available_from:

            return jsonify({
                "success": False,
                "message": (
                    "Available Until cannot be earlier "
                    "than Available From."
                )
            }), 400


    # ========================================================
    # 9. GENERATE UNIQUE LISTING ID
    # ========================================================

    listing_id = generate_listing_id()

    while db["produce"].find_one({
        "listing_id": listing_id
    }):

        listing_id = generate_listing_id()


    # ========================================================
    # 10. SAVE IMAGE
    # ========================================================

    backend_dir = Path(
        current_app.root_path
    )

    upload_dir = (
        backend_dir /
        "uploads" /
        "produce"
    )

    upload_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    original_filename = secure_filename(
        image.filename
    )

    extension = (
        original_filename
        .rsplit(".", 1)[1]
        .lower()
    )


    # UNIQUE FILE NAME
    unique_filename = (
        f"{listing_id}_"
        f"{uuid.uuid4().hex[:8]}."
        f"{extension}"
    )


    image_path = (
        upload_dir /
        unique_filename
    )


    try:

        image.save(
            str(image_path)
        )

    except Exception as error:

        current_app.logger.exception(
            "Unable to save uploaded image."
        )

        return jsonify({
            "success": False,
            "message": "Unable to save the uploaded image."
        }), 500


    # ========================================================
    # 11. IMAGE URL
    # ========================================================

    image_url = (
        f"/uploads/produce/{unique_filename}"
    )


    # ========================================================
    # 12. CREATE MONGODB DOCUMENT
    # ========================================================

    now = datetime.now(
        timezone.utc
    )


    listing = {

        # ----------------------------------------------------
        # IDs
        # ----------------------------------------------------

        "listing_id": listing_id,

        "farmer_id": farmer["_id"],

        "farmer_name": farmer.get(
            "name",
            ""
        ),


        # ----------------------------------------------------
        # PRODUCE
        # ----------------------------------------------------

        "produce_name": produce_name,

        "category": category,

        "description": description,


        # ----------------------------------------------------
        # QUANTITY
        # ----------------------------------------------------

        "quantity": quantity,

        "available_quantity": quantity,

        "unit": unit,

        "minimum_order": minimum_order_quantity,

        "minimum_order_quantity":
            minimum_order_quantity,


        # ----------------------------------------------------
        # PRICING
        # ----------------------------------------------------

        "price": price_per_unit,

        "price_per_unit": price_per_unit,

        "price_type": price_type,


        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        "location": {
            "address": location,
            "district": district,
            "state": state,
            "pincode": pincode
        },

        "pickup_instructions":
            pickup_instructions,

        "pickup_details":
            pickup_instructions,


        # ----------------------------------------------------
        # DATES
        # ----------------------------------------------------

        "harvest_date":
            harvest_date,

        "availability_date":
            available_from,

        "available_from":
            available_from,

        "available_until":
            available_until,


        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

        "image_url":
            image_url,

        "image_filename":
            unique_filename,

        "original_image_name":
            original_filename,


        # ----------------------------------------------------
        # QUALITY WORKFLOW
        # ----------------------------------------------------

        "status":
            "PENDING",

        "quality_status":
            "PENDING",

        "quality_id":
            None,


        # ----------------------------------------------------
        # ORDER WORKFLOW
        # ----------------------------------------------------

        "orders_count":
            0,

        "sold_quantity":
            0,


        # ----------------------------------------------------
        # TIMESTAMPS
        # ----------------------------------------------------

        "listed_at":
            now,

        "created_at":
            now,

        "updated_at":
            now,


        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        "source":
            "FARMER_UPLOAD"
    }


    # ========================================================
    # 13. INSERT INTO MONGODB
    # ========================================================

    try:

        result = db["produce"].insert_one(
            listing
        )

    except Exception as error:

        # If MongoDB insertion fails, remove the image
        # that was already saved so we don't leave orphan files.

        try:

            if image_path.exists():
                image_path.unlink()

        except Exception:

            current_app.logger.exception(
                "Could not remove orphaned image."
            )

        current_app.logger.exception(
            "Unable to create produce listing."
        )

        return jsonify({
            "success": False,
            "message": "Unable to create the produce listing."
        }), 500


    # ========================================================
    # 14. RESPONSE
    # ========================================================

    return jsonify({

        "success": True,

        "message": (
            "Produce listing created successfully "
            "and submitted for quality check."
        ),

        "listing": {

            "listing_id":
                listing_id,

            "produce_name":
                produce_name,

            "category":
                category,

            "quantity":
                quantity,

            "unit":
                unit,

            "minimum_order":
                minimum_order_quantity,

            "price_per_unit":
                price_per_unit,

            "price_type":
                price_type,

            "status":
                "PENDING",

            "quality_status":
                "PENDING",

            "image_url":
                image_url
        }

    }), 201
# ============================================================
# GET MY PRODUCE LISTINGS
# GET /api/listings/my
# ============================================================

@listing_bp.route("/api/listings/my", methods=["GET"])
@token_required
def get_my_listings():

    db = get_db()

    # ========================================================
    # 1. VERIFY FARMER
    # ========================================================

    farmer = get_current_farmer()

    if not farmer:

        return jsonify({
            "success": False,
            "message": "Only Farmer accounts can view their listings."
        }), 403

    # ========================================================
    # 2. FETCH ONLY THIS FARMER'S LISTINGS
    # ========================================================

    try:

        listings = list(
            db["produce"].find({
                "farmer_id": farmer["_id"]
            }).sort(
                "created_at",
                -1
            )

        )

    except Exception as error:

        current_app.logger.exception(
            "Unable to fetch farmer listings."
        )

        return jsonify({
            "success": False,
            "message": "Unable to load your listings."
        }), 500

    # ========================================================
    # 3. CONVERT MONGODB DOCUMENTS TO JSON
    # ========================================================

    result = []

    for listing in listings:

        listing_id = listing.get(
            "listing_id"
        )

        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        location_data = listing.get(
            "location",
            {}
        )

        if isinstance(
            location_data,
            dict
        ):

            location_text = location_data.get(
                "address",
                ""
            )

            # If address isn't available, build a readable
            # location from district/state.

            if not location_text:

                parts = [
                    location_data.get(
                        "district",
                        ""
                    ),
                    location_data.get(
                        "state",
                        ""
                    )
                ]

                location_text = ", ".join(
                    part
                    for part in parts
                    if part
                )

        else:

            location_text = str(
                location_data or ""
            )

        # ----------------------------------------------------
        # BUILD RESPONSE
        # ----------------------------------------------------

        result.append({

            "id":
                str(listing.get("_id"))
                if listing.get("_id")
                else None,

            "listing_id":
                listing_id,

            "farmer_id":
                str(farmer["_id"]),

            "farmer_name":
                listing.get(
                    "farmer_name",
                    farmer.get(
                        "name",
                        ""
                    )
                ),

            "produce_name":
                listing.get(
                    "produce_name",
                    ""
                ),

            "category":
                listing.get(
                    "category",
                    ""
                ),

            "description":
                listing.get(
                    "description",
                    ""
                ),

            "quantity":
                listing.get(
                    "quantity",
                    0
                ),

            "available_quantity":
                listing.get(
                    "available_quantity",
                    listing.get(
                        "quantity",
                        0
                    )
                ),

            "unit":
                listing.get(
                    "unit",
                    ""
                ),

            "minimum_order_quantity":
                listing.get(
                    "minimum_order_quantity",
                    listing.get(
                        "minimum_order",
                        0
                    )
                ),

            "price_per_unit":
                listing.get(
                    "price_per_unit",
                    listing.get(
                        "price",
                        0
                    )
                ),

            "price_type":
                listing.get(
                    "price_type",
                    "FIXED"
                ),

            "location":
                location_text,

            "district":
                location_data.get(
                    "district",
                    ""
                )
                if isinstance(
                    location_data,
                    dict
                )
                else "",

            "state":
                location_data.get(
                    "state",
                    ""
                )
                if isinstance(
                    location_data,
                    dict
                )
                else "",

            "pincode":
                location_data.get(
                    "pincode",
                    ""
                )
                if isinstance(
                    location_data,
                    dict
                )
                else "",

            "pickup_details":
                listing.get(
                    "pickup_details",
                    listing.get(
                        "pickup_instructions",
                        ""
                    )
                ),

            "harvest_date":
                listing.get(
                    "harvest_date"
                ).isoformat()
                if listing.get(
                    "harvest_date"
                )
                else None,

            "available_from":
                listing.get(
                    "available_from",
                    listing.get(
                        "availability_date"
                    )
                ).isoformat()
                if listing.get(
                    "available_from",
                    listing.get(
                        "availability_date"
                    )
                )
                else None,

            "available_until":
                listing.get(
                    "available_until"
                ).isoformat()
                if listing.get(
                    "available_until"
                )
                else None,

            "image_url":
                listing.get(
                    "image_url",
                    ""
                ),

            "image_filename":
                listing.get(
                    "image_filename",
                    ""
                ),

            "status":
                listing.get(
                    "status",
                    "PENDING"
                ),

            "quality_status":
                listing.get(
                    "quality_status",
                    "PENDING"
                ),

            "quality_id":
                listing.get(
                    "quality_id"
                ),

            "orders_count":
                listing.get(
                    "orders_count",
                    0
                ),

            "sold_quantity":
                listing.get(
                    "sold_quantity",
                    0
                ),

            "created_at":
                listing.get(
                    "created_at",
                    listing.get(
                        "listed_at"
                    )
                ).isoformat()
                if listing.get(
                    "created_at",
                    listing.get(
                        "listed_at"
                    )
                )
                else None,

            "updated_at":
                listing.get(
                    "updated_at"
                ).isoformat()
                if listing.get(
                    "updated_at"
                )
                else None
        })

    # ========================================================
    # 4. RESPONSE
    # ========================================================

    return jsonify({

        "success": True,

        "count":
            len(result),

        "listings":
            result

    }), 200
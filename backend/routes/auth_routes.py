from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta, timezone
from functools import wraps
from bson import ObjectId
import jwt

from models.user_model import UserModel
from utils.password_utils import (
    hash_password,
    verify_password
)


# ============================================================
# AUTH BLUEPRINT
# ============================================================

auth_bp = Blueprint("auth", __name__)
# ============================================================
# JWT AUTHENTICATION HELPER
# ============================================================

def token_required(f):

    @wraps(f)
    def decorated(*args, **kwargs):

        token = request.headers.get("Authorization")

        if not token:
            return jsonify({
                "success": False,
                "message": "Authentication token is required"
            }), 401

        # Expected format:
        # Authorization: Bearer <token>

        if not token.startswith("Bearer "):
            return jsonify({
                "success": False,
                "message": "Invalid authorization format"
            }), 401

        token = token.split(" ", 1)[1]

        try:

            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"]
            )

            request.user_id = payload["user_id"]

        except jwt.ExpiredSignatureError:

            return jsonify({
                "success": False,
                "message": "Session expired. Please login again."
            }), 401

        except jwt.InvalidTokenError:

            return jsonify({
                "success": False,
                "message": "Invalid authentication token"
            }), 401

        return f(*args, **kwargs)

    return decorated

# ============================================================
# SIGNUP
# POST /api/auth/signup
# ============================================================

@auth_bp.route("/signup", methods=["POST"])
def signup():

    data = request.get_json()

    # --------------------------------------------------------
    # Check request body
    # --------------------------------------------------------

    if not data:
        return jsonify({
            "success": False,
            "message": "Request body is required"
        }), 400


    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    required_fields = [
        "name",
        "email",
        "password",
        "phone",
        "address",
        "role"
    ]

    for field in required_fields:

        if not data.get(field):

            return jsonify({
                "success": False,
                "message": f"{field} is required"
            }), 400


    # --------------------------------------------------------
    # Get and clean values
    # --------------------------------------------------------

    name = data["name"].strip()

    email = data["email"].strip().lower()

    password = data["password"]

    phone = data["phone"].strip()

    address = data["address"].strip()

    role = data["role"].strip().upper()


    # --------------------------------------------------------
    # Validate role
    # --------------------------------------------------------

    allowed_roles = [
        "FARMER",
        "WHOLESALER",
        "VENDOR"
    ]

    if role not in allowed_roles:

        return jsonify({
            "success": False,
            "message": "Invalid role"
        }), 400


    # --------------------------------------------------------
    # Validate password
    # --------------------------------------------------------

    if len(password) < 8 or len(password) > 15:

        return jsonify({
            "success": False,
            "message": "Password must be between 8 and 15 characters"
        }), 400


    # --------------------------------------------------------
    # Get database
    # --------------------------------------------------------

    db = current_app.config["DB"]

    user_model = UserModel(db)


    # --------------------------------------------------------
    # Check duplicate email
    # --------------------------------------------------------

    existing_user = user_model.find_by_email(email)

    if existing_user:

        return jsonify({
            "success": False,
            "message": "An account with this email already exists"
        }), 409


    # --------------------------------------------------------
    # Create user
    # --------------------------------------------------------

    user = {

        "name": name,

        "email": email,

        "password_hash": hash_password(password),

        "phone": phone,

        "address": address,

        "role": role
    }


    user_id = user_model.create_user(user)


    # --------------------------------------------------------
    # Signup response
    # --------------------------------------------------------

    return jsonify({

        "success": True,

        "message": "Account created successfully",

        "user_id": user_id

    }), 201


# ============================================================
# LOGIN
# POST /api/auth/login
# ============================================================

@auth_bp.route("/login", methods=["POST"])
def login():

    data = request.get_json()


    # --------------------------------------------------------
    # Check request body
    # --------------------------------------------------------

    if not data:

        return jsonify({
            "success": False,
            "message": "Request body is required"
        }), 400


    # --------------------------------------------------------
    # Get login credentials
    # --------------------------------------------------------

    email = data.get("email", "").strip().lower()

    password = data.get("password", "")


    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if not email or not password:

        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400


    # --------------------------------------------------------
    # Get database
    # --------------------------------------------------------

    db = current_app.config["DB"]

    user_model = UserModel(db)


    # --------------------------------------------------------
    # Find user
    # --------------------------------------------------------

    user = user_model.find_by_email(email)


    # --------------------------------------------------------
    # Invalid email
    # --------------------------------------------------------

    if not user:

        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 401


    # --------------------------------------------------------
    # Verify password
    # --------------------------------------------------------

    password_correct = verify_password(
        password,
        user["password_hash"]
    )

    if not password_correct:

        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 401


    # --------------------------------------------------------
    # Create JWT payload
    # --------------------------------------------------------

    payload = {

        "user_id": str(user["_id"]),

        "email": user["email"],

        "role": user["role"],

        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }


    # --------------------------------------------------------
    # Generate JWT
    # --------------------------------------------------------

    token = jwt.encode(

        payload,

        current_app.config["JWT_SECRET"],

        algorithm="HS256"
    )


    # --------------------------------------------------------
    # Login response
    # --------------------------------------------------------

    return jsonify({

        "success": True,

        "message": "Login successful",

        "token": token,

        "user": {

            "id": str(user["_id"]),

            "name": user["name"],

            "email": user["email"],

            "role": user["role"]

        }

    }), 200
# ============================================================
# GET CURRENT USER PROFILE
# GET /api/auth/profile
# ============================================================

@auth_bp.route("/profile", methods=["GET"])
@token_required
def get_profile():

    db = current_app.config["DB"]

    user_model = UserModel(db)

    user = user_model.collection.find_one({
        "_id": ObjectId(request.user_id)
    })

    if not user:

        return jsonify({
            "success": False,
            "message": "User not found"
        }), 404

    return jsonify({
        "success": True,
        "user": {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "address": user.get("address", ""),
            "role": user.get("role", ""),
            "is_verified": user.get("is_verified", False),
            "created_at": (
                user["created_at"].isoformat()
                if user.get("created_at")
                else None
            )
        }
    }), 200
# ============================================================
# UPDATE CURRENT USER PROFILE
# PUT /api/auth/profile
# ============================================================

@auth_bp.route("/profile", methods=["PUT"])
@token_required
def update_profile():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "Request body is required"
        }), 400

    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    address = data.get("address", "").strip()

    if not name:

        return jsonify({
            "success": False,
            "message": "Name is required"
        }), 400

    if not phone:

        return jsonify({
            "success": False,
            "message": "Phone number is required"
        }), 400

    if not address:

        return jsonify({
            "success": False,
            "message": "Address is required"
        }), 400

    db = current_app.config["DB"]

    user_model = UserModel(db)

    result = user_model.collection.update_one(
        {
            "_id": ObjectId(request.user_id)
        },
        {
            "$set": {
                "name": name,
                "phone": phone,
                "address": address
            }
        }
    )

    if result.matched_count == 0:

        return jsonify({
            "success": False,
            "message": "User not found"
        }), 404

    return jsonify({
        "success": True,
        "message": "Profile updated successfully"
    }), 200
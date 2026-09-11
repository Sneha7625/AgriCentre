from flask import Flask, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import os
from routes.meeting_routes import meeting_bp
from config import Config
from routes.auth_routes import auth_bp
from routes.contact_routes import contact_bp
from routes.dashboard_routes import dashboard_bp
from routes.listing_routes import listing_bp
from routes.order_routes import order_bp
from routes.buyer_routes import buyer_bp
from routes.logistics_routes import logistics_bp
from flask_cors import CORS
from routes.subscription_routes import subscription_bp
from routes.marketplace_routes import marketplace_bp
from routes.wholesaler_offer import wholesaler_offer_bp
from routes.payment_routes import payment_bp
from routes.demand_forecast_routes import demand_forecast_bp
# ----------------------------------
# -----------
# -----
# CREATE FLASK APP
# --------------------------------------------------

app = Flask(__name__)
from flask_cors import CORS

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "http://127.0.0.1:5500",
                "http://localhost:5500"
            ],
            "methods": [
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "OPTIONS"
            ],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "X-User-ID"
            ],
            "supports_credentials": True
        }
    }
)

# Load configuration from config.py
app.config.from_object(Config)

# Allow frontend to communicate with backend


# --------------------------------------------------
# MONGODB CONNECTION
# --------------------------------------------------

client = MongoClient(app.config["MONGO_URI"])

# Select database
db = client[app.config["DB_NAME"]]

# Store database object in Flask config
app.config["DB"] = db

app.register_blueprint(
    auth_bp,
    url_prefix="/api/auth"
)
app.register_blueprint(contact_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(listing_bp)
app.register_blueprint(order_bp)
app.register_blueprint(buyer_bp)
from routes.offer_routes import offer_bp
app.register_blueprint(logistics_bp)
app.register_blueprint(offer_bp)
app.register_blueprint(meeting_bp)
app.register_blueprint(subscription_bp)
app.register_blueprint(marketplace_bp)
app.register_blueprint(wholesaler_offer_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(demand_forecast_bp)
# --------------------------------------------------
# BASIC ROUTES
# --------------------------------------------------

@app.route("/")
def home():
    return {
        "message": "AgriCentre Backend is running!"
    }, 200


@app.route("/api/health")
def health_check():
    try:
        # Test MongoDB connection
        client.admin.command("ping")

        return {
            "status": "success",
            "message": "Flask and MongoDB are connected!"
        }, 200

    except PyMongoError as e:
        return {
            "status": "error",
            "message": "MongoDB connection failed",
            "error": str(e)
        }, 500


# --------------------------------------------------
# DATABASE DEBUG ROUTE
# TEMPORARY - REMOVE BEFORE DEPLOYMENT
# --------------------------------------------------

@app.route("/api/debug/db")
def debug_database():
    try:
        databases = client.list_database_names()

        return {
            "connected": True,
            "current_database": app.config["DB_NAME"],
            "databases": databases,
            "users_count": db["users"].count_documents({})
        }, 200

    except PyMongoError as e:
        return {
            "connected": False,
            "error": str(e)
        }, 500


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------
@app.route("/uploads/produce/<path:filename>")
def serve_produce_image(filename):

    upload_folder = os.path.join(
        app.root_path,
        "uploads",
        "produce"
    )

    return send_from_directory(
        upload_folder,
        filename
    )
if __name__ == "__main__":
    app.run(
        debug=True,
        port=5000
    )
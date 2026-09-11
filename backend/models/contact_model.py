from datetime import datetime
from bson import ObjectId


def create_contact_document(name, email, category, message):
    return {
        "name": name,
        "email": email,
        "category": category,
        "message": message,
        "type": "contact",
        "status": "pending",
        "created_at": datetime.utcnow()
    }


def create_feedback_document(name, email, category, message):
    return {
        "name": name,
        "email": email,
        "category": category,
        "message": message,
        "type": "feedback",
        "status": "pending",
        "created_at": datetime.utcnow()
    }
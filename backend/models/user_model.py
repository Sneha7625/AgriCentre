from datetime import datetime
from bson import ObjectId


class UserModel:

    def __init__(self, db):
        self.collection = db["users"]

    def create_user(self, user_data):
        user_data["created_at"] = datetime.utcnow()
        user_data["is_verified"] = False

        result = self.collection.insert_one(user_data)

        return str(result.inserted_id)

    def find_by_email(self, email):
        return self.collection.find_one({"email": email.lower().strip()})
from datetime import datetime, timezone
from bson import ObjectId


class ListingModel:

    COLLECTION_NAME = "listings"

    def __init__(self, db):
        self.collection = db[self.COLLECTION_NAME]

    # ========================================================
    # CREATE LISTING
    # ========================================================

    def create_listing(self, listing_data):

        now = datetime.now(timezone.utc)

        listing_data["created_at"] = now
        listing_data["updated_at"] = now

        result = self.collection.insert_one(listing_data)

        return str(result.inserted_id)

    # ========================================================
    # FIND LISTING BY ID
    # ========================================================

    def find_by_id(self, listing_id):

        try:
            object_id = ObjectId(listing_id)
        except Exception:
            return None

        return self.collection.find_one({
            "_id": object_id
        })

    # ========================================================
    # FIND ALL LISTINGS OF A FARMER
    # ========================================================

    def find_by_farmer(self, farmer_id):

        return list(
            self.collection.find({
                "farmer_id": str(farmer_id)
            }).sort(
                "created_at",
                -1
            )
        )

    # ========================================================
    # FIND ACTIVE LISTINGS
    # ========================================================

    def find_active_listings(self):

        return list(
            self.collection.find({
                "status": "ACTIVE"
            }).sort(
                "created_at",
                -1
            )
        )

    # ========================================================
    # UPDATE LISTING
    # ========================================================

    def update_listing(
        self,
        listing_id,
        update_data
    ):

        try:
            object_id = ObjectId(listing_id)
        except Exception:
            return False

        update_data["updated_at"] = datetime.now(
            timezone.utc
        )

        result = self.collection.update_one(
            {
                "_id": object_id
            },
            {
                "$set": update_data
            }
        )

        return result.matched_count > 0

    # ========================================================
    # DELETE LISTING
    # ========================================================

    def delete_listing(self, listing_id):

        try:
            object_id = ObjectId(listing_id)
        except Exception:
            return False

        result = self.collection.delete_one({
            "_id": object_id
        })

        return result.deleted_count > 0

    # ========================================================
    # COUNT FARMER LISTINGS
    # ========================================================

    def count_by_farmer(self, farmer_id):

        return self.collection.count_documents({
            "farmer_id": str(farmer_id)
        })

    # ========================================================
    # COUNT ACTIVE FARMER LISTINGS
    # ========================================================

    def count_active_by_farmer(self, farmer_id):

        return self.collection.count_documents({
            "farmer_id": str(farmer_id),
            "status": "ACTIVE"
        })
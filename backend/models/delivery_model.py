from datetime import datetime

from flask import current_app


class DeliveryModel:

    def __init__(self):
        self.collection = current_app.config["DB"]["deliveries"]
    def get_all_deliveries(self):
        """
        Get all deliveries.
        """

        return list(
            self.collection.find(
                {},
                {
                    "_id": 0
                }
            ).sort(
                "scheduled_at",
                -1
            )
        )

    def get_delivery_by_id(self, delivery_id):
        """
        Get a delivery using delivery_id.
        """

        return self.collection.find_one(
            {
                "delivery_id": delivery_id
            },
            {
                "_id": 0
            }
        )

    def get_deliveries_by_farmer(self, farmer_id):
        """
        Get all deliveries belonging to a farmer.

        Supports both ObjectId and string farmer_id values
        because older/demo documents may use either format.
        """

        from bson import ObjectId

        farmer_ids = [
            str(farmer_id)
        ]

        try:

            farmer_ids.append(
                ObjectId(
                    str(farmer_id)
                )
            )

        except Exception:

            pass

        return list(
            self.collection.find(
                {
                    "farmer_id": {
                        "$in": farmer_ids
                    }
                },
                {
                    "_id": 0
                }
            ).sort(
                "scheduled_at",
                -1
            )
        )
    def get_deliveries_by_buyer(self, buyer_id):
        """
        Get all deliveries belonging to a buyer.
        """

        return list(
            self.collection.find(
                {
                    "buyer_id": buyer_id
                },
                {
                    "_id": 0
                }
            ).sort(
                "scheduled_at",
                -1
            )
        )

    def get_active_deliveries_by_farmer(self, farmer_id):
        """
        Get farmer deliveries that are still active.
        """

        active_statuses = [
            "SCHEDULED",
            "ASSIGNED",
            "PICKUP_PENDING",
            "PICKED_UP",
            "IN_TRANSIT"
        ]

        return list(
            self.collection.find(
                {
                    "farmer_id": farmer_id,
                    "status": {
                        "$in": active_statuses
                    }
                },
                {
                    "_id": 0
                }
            ).sort(
                "scheduled_at",
                1
            )
        )

    def create_delivery(self, delivery_data):
        """
        Create a new delivery.
        """

        if "delivery_id" not in delivery_data:
            raise ValueError(
                "delivery_id is required"
            )

        if "order_id" not in delivery_data:
            raise ValueError(
                "order_id is required"
            )

        existing_delivery = self.collection.find_one(
            {
                "delivery_id": delivery_data["delivery_id"]
            }
        )

        if existing_delivery:
            raise ValueError(
                "Delivery with this delivery_id already exists"
            )

        self.collection.insert_one(delivery_data)

        return self.get_delivery_by_id(
            delivery_data["delivery_id"]
        )

    def update_delivery_status(
        self,
        delivery_id,
        status
    ):
        """
        Update the shipment status.
        """

        allowed_statuses = [
            "SCHEDULED",
            "ASSIGNED",
            "PICKUP_PENDING",
            "PICKED_UP",
            "IN_TRANSIT",
            "DELIVERED",
            "CANCELLED"
        ]

        status = status.upper()

        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid delivery status: {status}"
            )

        result = self.collection.update_one(
            {
                "delivery_id": delivery_id
            },
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return result.modified_count > 0

    def update_delivery_route(
        self,
        delivery_id,
        distance_km,
        estimated_cost,
        eta_hours
    ):
        """
        Update route-related information.
        """

        result = self.collection.update_one(
            {
                "delivery_id": delivery_id
            },
            {
                "$set": {
                    "distance_km": distance_km,
                    "estimated_cost": estimated_cost,
                    "eta_hours": eta_hours,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return result.modified_count > 0

    def delete_delivery(self, delivery_id):
        """
        Delete a delivery.
        """

        result = self.collection.delete_one(
            {
                "delivery_id": delivery_id
            }
        )

        return result.deleted_count > 0
from datetime import datetime
from flask import current_app

class DriverModel:

    def __init__(self):
        self.collection = current_app.config["DB"]["drivers"]
    def get_all_drivers(self, status=None):
        """
        Get all active drivers.

        If status is provided, only drivers with
        that status are returned.
        """

        query = {
            "is_active": True
        }

        if status:
            query["status"] = status.upper()

        return list(
            self.collection.find(
                query,
                {
                    "_id": 0
                }
            )
        )

    def get_available_drivers(self):
        """
        Get all active drivers who are currently available.
        """

        return self.get_all_drivers("AVAILABLE")

    def get_driver_by_id(self, driver_id):
        """
        Get one active driver by driver_id.
        """

        return self.collection.find_one(
            {
                "driver_id": driver_id,
                "is_active": True
            },
            {
                "_id": 0
            }
        )

    def update_driver_status(self, driver_id, status):
        """
        Update the status of a driver.
        """

        allowed_statuses = [
            "AVAILABLE",
            "ASSIGNED",
            "ON_TRIP",
            "OFFLINE"
        ]

        status = status.upper()

        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid driver status: {status}"
            )

        result = self.collection.update_one(
            {
                "driver_id": driver_id,
                "is_active": True
            },
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return result.modified_count > 0

    def assign_driver(self, driver_id):
        """
        Atomically assign an AVAILABLE driver.

        The driver will only be assigned if they are
        currently AVAILABLE.
        """

        result = self.collection.update_one(
            {
                "driver_id": driver_id,
                "status": "AVAILABLE",
                "is_active": True
            },
            {
                "$set": {
                    "status": "ASSIGNED",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return result.modified_count > 0

    def release_driver(self, driver_id):
        """
        Make a driver available again.
        """

        result = self.collection.update_one(
            {
                "driver_id": driver_id,
                "is_active": True
            },
            {
                "$set": {
                    "status": "AVAILABLE",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return result.modified_count > 0
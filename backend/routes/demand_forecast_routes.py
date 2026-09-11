from flask import Blueprint, jsonify, request
from pathlib import Path
import json


# ============================================================
# BLUEPRINT
# ============================================================

demand_forecast_bp = Blueprint(
    "demand_forecast",
    __name__
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ML_DATA_DIR = BASE_DIR / "ml_data"
ML_MODELS_DIR = BASE_DIR / "ml_models"

FORECAST_FILE = (
    ML_MODELS_DIR / "forecast_api_data.json"
)

CONFIG_FILE = (
    ML_MODELS_DIR / "demand_forecasting_config_final.json"
)

MODEL_FILE = (
    ML_MODELS_DIR / "demand_forecasting_model_final.pkl"
)


# ============================================================
# LOAD JSON
# ============================================================

def load_json(path):

    if not path.exists():

        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# EXTRACT FORECASTS
# ============================================================

def extract_crops(data):

    # Case 1:
    # JSON itself is a list

    if isinstance(data, list):

        return data


    if not isinstance(data, dict):

        return []


    # Case 2:
    # {"crops": [...]}

    if isinstance(
        data.get("crops"),
        list
    ):

        return data["crops"]


    # Case 3:
    # {"forecasts": [...]}

    if isinstance(
        data.get("forecasts"),
        list
    ):

        return data["forecasts"]


    # Case 4:
    # {"data": {"crops": [...]}}

    nested = data.get("data")

    if isinstance(
        nested,
        dict
    ):

        if isinstance(
            nested.get("crops"),
            list
        ):

            return nested["crops"]


        if isinstance(
            nested.get("forecasts"),
            list
        ):

            return nested["forecasts"]


    return []


# ============================================================
# NORMALIZE CROP DATA
# ============================================================

def normalize_crop(item):

    return {

        "crop":
            item.get("crop")
            or item.get("crop_name")
            or item.get("commodity")
            or "Unknown",


        "forecast_week":
            item.get("forecast_week")
            or item.get("week")
            or item.get("forecast_date")
            or "—",


        "last_observed_arrivals_tonnes":
            item.get(
                "last_observed_arrivals_tonnes"
            )
            if item.get(
                "last_observed_arrivals_tonnes"
            ) is not None
            else item.get(
                "last_observed",
                item.get(
                    "last_arrivals_tonnes"
                )
            ),


        "predicted_arrivals_tonnes":
            item.get(
                "predicted_arrivals_tonnes"
            )
            if item.get(
                "predicted_arrivals_tonnes"
            ) is not None
            else item.get(
                "predicted",
                item.get(
                    "predicted_tonnes"
                )
            ),


        "predicted_change_percent":
            item.get(
                "predicted_change_percent"
            )
            if item.get(
                "predicted_change_percent"
            ) is not None
            else item.get(
                "change_percent",
                item.get("change")
            ),


        "forecast_direction":
            str(
                item.get(
                    "forecast_direction",
                    item.get(
                        "direction",
                        "stable"
                    )
                )
            ).strip().lower(),


        "insight_message":
            item.get(
                "insight_message",
                item.get(
                    "insight",
                    "Forecast indicates the expected market activity for this crop."
                )
            )
    }


# ============================================================
# SUMMARY
# ============================================================

def build_summary(
    original_data,
    crops
):

    source_summary = {}

    if isinstance(
        original_data,
        dict
    ):

        source_summary = (
            original_data.get(
                "summary"
            )
            or {}
        )

        if isinstance(
            original_data.get("data"),
            dict
        ):

            source_summary = (
                original_data["data"].get(
                    "summary"
                )
                or source_summary
            )


    directions = [

        crop.get(
            "forecast_direction",
            "stable"
        )

        for crop in crops

    ]


    return {

        "crops_forecasted":
            source_summary.get(
                "crops_forecasted",
                source_summary.get(
                    "total_crops",
                    len(crops)
                )
            ),

        "increasing":
            source_summary.get(
                "increasing",
                directions.count(
                    "increasing"
                )
            ),

        "stable":
            source_summary.get(
                "stable",
                directions.count(
                    "stable"
                )
            ),

        "decreasing":
            source_summary.get(
                "decreasing",
                directions.count(
                    "decreasing"
                )
            )
    }


# ============================================================
# ROLE-SPECIFIC INFORMATION
# ============================================================

def role_information(role):

    role = str(
        role or "VENDOR"
    ).strip().upper()


    # --------------------------------------------------------
    # VENDOR
    # --------------------------------------------------------

    if role == "VENDOR":

        return {

            "role": "VENDOR",

            "title":
                "Vendor Purchase & Inventory Support",

            "message":
                (
                    "Use expected market activity "
                    "to plan purchases, inventory "
                    "and order timing. Rising arrivals "
                    "can indicate greater market "
                    "availability, while falling arrivals "
                    "may require earlier supply planning."
                )
        }


    # --------------------------------------------------------
    # WHOLESALER
    # --------------------------------------------------------

    if role == "WHOLESALER":

        return {

            "role": "WHOLESALER",

            "title":
                "Wholesaler Procurement Support",

            "message":
                (
                    "Use expected market arrivals "
                    "to plan bulk procurement, "
                    "supplier coordination and "
                    "inventory. Crop-level trends "
                    "can help prioritize when "
                    "to secure supply."
                )
        }


    # --------------------------------------------------------
    # FARMER
    # --------------------------------------------------------

    if role == "FARMER":

        return {

            "role": "FARMER",

            "title":
                "Farmer Selling Support",

            "message":
                (
                    "Use expected market activity "
                    "as one input for selling and "
                    "supply planning. Crop-level trends "
                    "can help identify periods of "
                    "stronger or weaker expected "
                    "market activity."
                )
        }


    return {

        "role": role,

        "title":
            "Demand Forecasting",

        "message":
            "Demand forecasting information is available."
    }


# ============================================================
# DEMAND FORECAST
# ============================================================

@demand_forecast_bp.route(
    "/api/demand-forecast",
    methods=["GET"]
)
def get_demand_forecast():

    try:

        # ----------------------------------------------------
        # LOAD FINAL FORECAST OUTPUT
        # ----------------------------------------------------

        forecast_data = load_json(
            FORECAST_FILE
        )


        raw_crops = extract_crops(
            forecast_data
        )


        if not raw_crops:

            return jsonify({

                "success": False,

                "message":
                    "No crop forecast data found."

            }), 500


        crops = [

            normalize_crop(
                crop
            )

            for crop in raw_crops

            if isinstance(
                crop,
                dict
            )

        ]


        crops = [

            crop

            for crop in crops

            if crop["crop"] != "Unknown"

        ]


        # ----------------------------------------------------
        # GET USER ROLE
        # ----------------------------------------------------

        role = request.args.get(
            "role",
            "VENDOR"
        )


        role_data = role_information(
            role
        )


        # ----------------------------------------------------
        # MODEL CONFIG
        # ----------------------------------------------------

        config = {}

        if CONFIG_FILE.exists():

            try:

                config = load_json(
                    CONFIG_FILE
                )

            except Exception:

                config = {}


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        response = {

            "success": True,

            "data": {

                "summary":
                    build_summary(
                        forecast_data,
                        crops
                    ),


                "model": {

                    "name":
                        "XGBoost",

                    "status":
                        "FINAL",

                    "forecast_horizon_days":
                        7,

                    "crops_supported":
                        len(crops),

                    "performance": {

                        "naive_wape":
                            23.10,

                        "final_wape":
                            20.80,

                        "improvement_percent":
                            9.98
                    }
                },


                "role":
                    role_data,


                "crops":
                    crops,


                "source": {

                    "type":
                        "Historical mandi market-arrival data",

                    "latest_data_note":
                        (
                            "Forecasts are based on "
                            "the historical market-arrival "
                            "data used to train the final "
                            "AgriCentre model."
                        )
                }
            }
        }


        # ----------------------------------------------------
        # CONFIG INFORMATION
        # ----------------------------------------------------

        if isinstance(
            config,
            dict
        ):

            response["data"]["config"] = {

                "feature_columns":
                    config.get(
                        "feature_columns"
                    ),

                "target":
                    config.get(
                        "target"
                    ),

                "latest_date":
                    config.get(
                        "latest_date"
                    ),

                "forecast_horizon":
                    config.get(
                        "forecast_horizon"
                    )
            }


        return jsonify(
            response
        ), 200


    except FileNotFoundError as error:

        return jsonify({

            "success": False,

            "message":
                str(error)

        }), 500


    except Exception as error:

        print(
            "Demand Forecast Error:",
            error
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to load demand forecast.",

            "error":
                str(error)

        }), 500


# ============================================================
# SINGLE CROP
# ============================================================

@demand_forecast_bp.route(
    "/api/demand-forecast/<crop>",
    methods=["GET"]
)
def get_single_crop_forecast(
    crop
):

    try:

        forecast_data = load_json(
            FORECAST_FILE
        )


        crops = [

            normalize_crop(
                item
            )

            for item in extract_crops(
                forecast_data
            )

            if isinstance(
                item,
                dict
            )

        ]


        for item in crops:

            if (
                str(
                    item["crop"]
                ).strip().lower()
                ==
                crop.strip().lower()
            ):

                return jsonify({

                    "success": True,

                    "data":
                        item

                }), 200


        return jsonify({

            "success": False,

            "message":
                f"No forecast found for crop: {crop}"

        }), 404


    except Exception as error:

        return jsonify({

            "success": False,

            "message":
                str(error)

        }), 500
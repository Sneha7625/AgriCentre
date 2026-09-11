from flask import Blueprint, request, jsonify, current_app, g
from bson import ObjectId
from datetime import datetime, timezone
import secrets
import re

from routes.auth_routes import token_required
from utils.email_service import send_email
from models.driver_model import DriverModel

meeting_bp = Blueprint("meeting", __name__)


# ============================================================
# HELPERS
# ============================================================

ALLOWED_ROLES = {
    "FARMER": "Farmer",
    "WHOLESALER": "Bulk Buyer",
    "VENDOR": "Buyer / Consumer",
    "DRIVER": "Driver"
}


def get_db():
    return current_app.config["DB"]


def get_current_user():
    db = get_db()

    try:
        user_id = ObjectId(request.user_id)
    except Exception:
        return None

    return db["users"].find_one({"_id": user_id})


def clean_text(value, max_length=200):
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())[:max_length]


def valid_date(value):
    if not isinstance(value, str):
        return None

    try:
        return datetime.strptime(
            value.strip(),
            "%Y-%m-%d"
        ).date()
    except ValueError:
        return None


def valid_time(value):
    if not isinstance(value, str):
        return False

    return bool(
        re.fullmatch(
            r"^(?:[01]\d|2[0-3]):[0-5]\d$",
            value.strip()
        )
    )


def serialize_user(user):

    role = str(
        user.get("role", "")
    ).strip().upper()


    # --------------------------------------------------------
    # LOCATION
    #
    # Prefer the explicitly stored location.
    # If it is empty, fall back to address.
    # If that is also unavailable, build it from city/state.
    # --------------------------------------------------------

    location = str(
        user.get("location") or ""
    ).strip()


    if not location:

        location = str(
            user.get("address") or ""
        ).strip()


    if not location:

        location = ", ".join(
            value
            for value in [
                user.get("city", ""),
                user.get("state", "")
            ]
            if value
        )


    return {

        "id":
            str(user["_id"]),

        "name":
            user.get("name", ""),

        "email":
            user.get("email", ""),

        "role":
            role,

        "role_label":
            ALLOWED_ROLES.get(
                role,
                role
            ),

        "phone":
            user.get("phone", ""),

        "location":
            location,

        # Keep these too — useful for the
        # participant card/details later.
        "address":
            user.get("address", ""),

        "city":
            user.get("city", ""),

        "district":
            user.get("district", ""),

        "state":
            user.get("state", ""),

        "pincode":
            user.get("pincode", "")

    }

def generate_meeting_id():
    # Human-readable but sufficiently unpredictable room ID.
    return (
        "AGR-"
        + secrets.token_hex(4).upper()
        + "-"
        + secrets.token_hex(3).upper()
    )


def build_jitsi_link(meeting_id):
    # Jitsi public instance. The room name is unique and generated
    # by the backend, not by the browser.
    return (
        "https://meet.jit.si/"
        + meeting_id
    )

# ============================================================
# SEARCH PARTICIPANT - CORS PREFLIGHT
# ============================================================

@meeting_bp.route(
    "/api/meetings/search-participants",
    methods=["OPTIONS"],
    provide_automatic_options=False
)
def search_participants_preflight():

    return "", 204


# ============================================================
# SEARCH OTHER PARTICIPANT
#
# GET /api/meetings/search-participants?role=FARMER&name=Sneha
# ============================================================

@meeting_bp.route(
    "/api/meetings/search-participants",
    methods=["GET"],
    provide_automatic_options=False
)
@token_required
def search_participants():

    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "success": False,
            "message": "Current user not found."
        }), 404


    role = clean_text(
        request.args.get("role", ""),
        30
    ).upper()


    name = clean_text(
        request.args.get("name", ""),
        100
    )


    # --------------------------------------------------------
    # VALIDATE ROLE
    # --------------------------------------------------------

    if role not in ALLOWED_ROLES:

        return jsonify({
            "success": False,
            "message": "Please select a valid participant role."
        }), 400


    # --------------------------------------------------------
    # VALIDATE NAME
    # --------------------------------------------------------

    if len(name) < 2:

        return jsonify({
            "success": False,
            "message": (
                "Enter at least 2 characters "
                "of the person's name."
            )
        }), 400


    # ========================================================
    # DRIVER SEARCH
    #
    # Drivers are stored separately from users.
    # ========================================================

    if role == "DRIVER":

        from models.driver_model import DriverModel

        driver_model = DriverModel()

        drivers = driver_model.get_all_drivers()

        search_name = name.lower()

        participants = []


        for driver in drivers:

            driver_name = str(
                driver.get("name", "")
            ).strip()


            if search_name not in driver_name.lower():
                continue


            location = str(
                driver.get("location")
                or driver.get("address")
                or ""
            ).strip()


            participants.append({

                "id": str(
                    driver.get(
                        "driver_id",
                        ""
                    )
                ),

                "name": driver_name,

                "email": driver.get(
                    "email",
                    ""
                ),

                "phone": driver.get(
                    "phone",
                    ""
                ),

                "role": "DRIVER",

                "role_label": "Driver",

                "location": location,

                "vehicle_number": driver.get(
                    "vehicle_number",
                    ""
                ),

                "status": driver.get(
                    "status",
                    ""
                )

            })


            if len(participants) >= 10:
                break


        return jsonify({

            "success": True,

            "participants":
                participants,

            "count":
                len(participants)

        }), 200


    # ========================================================
    # FARMER / BULK BUYER / BUYER-CONSUMER
    # ========================================================

    db = get_db()


    query = {

        "_id": {
            "$ne":
                current_user["_id"]
        },

        "role":
            role,

        "name": {

            "$regex":
                re.escape(name),

            "$options":
                "i"
        }

    }


    users = list(

        db["users"]
        .find(query)
        .sort("name", 1)
        .limit(10)

    )


    participants = [

        serialize_user(user)

        for user in users

    ]


    return jsonify({

        "success": True,

        "participants":
            participants,

        "count":
            len(participants)

    }), 200
# ============================================================
# GET LOGGED-IN USER PROFILE FOR MEETING PAGE
#
# GET /api/meetings/me
# ============================================================

@meeting_bp.route(
    "/api/meetings/me",
    methods=["OPTIONS"],
    provide_automatic_options=False
)
def meetings_me_preflight():

    return "", 204


@meeting_bp.route(
    "/api/meetings/me",
    methods=["GET"],
    provide_automatic_options=False
)
@token_required
def get_me():

    user = get_current_user()

    if not user:
        return jsonify({
            "success": False,
            "message": "User profile not found."
        }), 404

    return jsonify({
        "success": True,
        "user": serialize_user(user)
    }), 200


# ============================================================
# GET PARTICIPANT BY ID
#
# Useful when the user arrived from:
# Find Buyers -> Schedule Meeting
# meeting.html?buyer_id=<id>
# ============================================================

@meeting_bp.route(
    "/api/meetings/participant/<user_id>",
    methods=["OPTIONS"],
    provide_automatic_options=False
)
def participant_preflight(user_id):

    return "", 204


@meeting_bp.route(
    "/api/meetings/participant/<user_id>",
    methods=["GET"],
    provide_automatic_options=False
)
@token_required
def get_participant(user_id):

    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "success": False,
            "message": "Current user not found."
        }), 404

    try:
        participant_id = ObjectId(user_id)
    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid participant ID."
        }), 400

    if participant_id == current_user["_id"]:
        return jsonify({
            "success": False,
            "message": "You cannot schedule a meeting with yourself."
        }), 400

    db = get_db()

    participant = db["users"].find_one({
        "_id": participant_id
    })

    if not participant:
        return jsonify({
            "success": False,
            "message": "Participant not found."
        }), 404

    role = str(
        participant.get("role", "")
    ).strip().upper()

    if role not in ALLOWED_ROLES:
        return jsonify({
            "success": False,
            "message": "This user cannot be selected for a meeting."
        }), 400

    return jsonify({
        "success": True,
        "participant": serialize_user(participant)
    }), 200


# ============================================================
# SCHEDULE MEETING
#
# POST /api/meetings/schedule
#
# Body:
# {
#   "participant_id": "...",
#   "date": "2026-09-15",
#   "time": "15:30",
#   "purpose": "Discuss produce order"
# }
#
# The organizer is ALWAYS taken from the JWT.
# ============================================================

@meeting_bp.route(
    "/api/meetings/schedule",
    methods=["OPTIONS"],
    provide_automatic_options=False
)
def schedule_meeting_preflight():

    return "", 204


@meeting_bp.route(
    "/api/meetings/schedule",
    methods=["POST"],
    provide_automatic_options=False
)
@token_required
def schedule_meeting():

    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "success": False,
            "message": "Current user not found."
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Request body must be valid JSON."
        }), 400

    participant_id_raw = str(
        data.get("participant_id", "")
    ).strip()

    try:
        participant_id = ObjectId(
            participant_id_raw
        )
    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid participant ID."
        }), 400

    if participant_id == current_user["_id"]:
        return jsonify({
            "success": False,
            "message": "You cannot schedule a meeting with yourself."
        }), 400

    meeting_date = valid_date(
        data.get("date")
    )

    if not meeting_date:
        return jsonify({
            "success": False,
            "message": "Please provide a valid meeting date."
        }), 400

    if not valid_time(
        data.get("time")
    ):
        return jsonify({
            "success": False,
            "message": "Please provide a valid meeting time."
        }), 400

    purpose = clean_text(
        data.get("purpose", ""),
        500
    )

    if len(purpose) < 3:
        return jsonify({
            "success": False,
            "message": "Please provide a meeting purpose."
        }), 400

    db = get_db()

    participant = db["users"].find_one({
        "_id": participant_id
    })

    if not participant:
        return jsonify({
            "success": False,
            "message": "Selected participant was not found."
        }), 404

    participant_role = str(
        participant.get("role", "")
    ).strip().upper()

    if participant_role not in ALLOWED_ROLES:
        return jsonify({
            "success": False,
            "message": "Selected participant cannot be scheduled."
        }), 400

    # Generate the room only on the backend.
    meeting_id = generate_meeting_id()
    meeting_link = build_jitsi_link(meeting_id)

    created_at = datetime.now(timezone.utc)

    meeting_document = {
        "meeting_id": meeting_id,
        "meeting_link": meeting_link,

        "organizer_id": current_user["_id"],
        "organizer_name": current_user.get(
            "name",
            ""
        ),
        "organizer_email": current_user.get(
            "email",
            ""
        ),
        "organizer_role": current_user.get(
            "role",
            ""
        ),

        "participant_id": participant["_id"],
        "participant_name": participant.get(
            "name",
            ""
        ),
        "participant_email": participant.get(
            "email",
            ""
        ),
        "participant_role": participant_role,

        "date": meeting_date.isoformat(),
        "time": data["time"].strip(),

        "purpose": purpose,

        "status": "scheduled",

        "created_at": created_at,

        "email_status": "pending",
        "organizer_email_sent": False,
        "participant_email_sent": False
    }

    result = db[
        "meetings"
    ].insert_one(
        meeting_document
    )

    # ============================================================
    # SEND MEETING EMAILS
    # ============================================================

    organizer_name = current_user.get(
        "name",
        "AgriCentre User"
    )

    organizer_email = current_user.get(
        "email",
        ""
    ).strip()

    organizer_role = current_user.get(
        "role",
        ""
    )

    participant_name = participant.get(
        "name",
        "AgriCentre User"
    )

    participant_email = participant.get(
        "email",
        ""
    ).strip()

    participant_role = participant_role


    # ============================================================
    # COMMON MEETING DETAILS
    # ============================================================

    common_details = f"""
    Meeting ID: {meeting_id}

    Meeting Link:
    {meeting_link}

    Date:
    {meeting_date.strftime("%d %B %Y")}

    Time:
    {data["time"].strip()}

    Purpose:
    {purpose}
    """


    # ============================================================
    # EMAIL ORGANIZER
    # ============================================================

    organizer_sent = False

    if organizer_email:

        organizer_subject = (
            "AgriCentre Meeting Scheduled — "
            + participant_name
        )

        organizer_body = f"""
    Hello {organizer_name},

    Your AgriCentre meeting has been scheduled successfully.

    You are meeting:
    {participant_name}

    Participant Role:
    {ALLOWED_ROLES.get(
        participant_role,
        participant_role
    )}

    {common_details}

    Please join the meeting using the link above at the
    scheduled date and time.

    Regards,
    AgriCentre Team
    """

        organizer_sent = send_email(
            organizer_email,
            organizer_subject,
            organizer_body
        )


    # ============================================================
    # EMAIL PARTICIPANT
    # ============================================================

    participant_sent = False

    if participant_email:

        participant_subject = (
            "AgriCentre Meeting Invitation — "
            + organizer_name
        )

        participant_body = f"""
    Hello {participant_name},

    You have been invited to an AgriCentre meeting.

    Meeting arranged by:
    {organizer_name}

    Organizer Role:
    {ALLOWED_ROLES.get(
        organizer_role,
        organizer_role
    )}

    {common_details}

    Please join the meeting using the link above at the
    scheduled date and time.

    Regards,
    AgriCentre Team
    """

        participant_sent = send_email(
            participant_email,
            participant_subject,
            participant_body
        )


    # ============================================================
    # EMAIL AGRICENTRE TEAM
    #
    # For now, AgriCentre also receives every meeting
    # notification so we can track all scheduled meetings.
    # ============================================================

    admin_email = (
        current_app.config.get("CONTACT_RECEIVER")
        or current_app.config.get("MAIL_USERNAME")
    )

    admin_sent = False

    if admin_email:

        admin_subject = (
            "New AgriCentre Meeting Scheduled — "
            + organizer_name
        )

        admin_body = f"""
    Hello AgriCentre Team,

    A new meeting has been scheduled through
    the AgriCentre Meeting Centre.

    ORGANIZER
    --------------------------------------------------
    Name: {organizer_name}
    Email: {organizer_email}
    Role: {ALLOWED_ROLES.get(
        organizer_role,
        organizer_role
    )}

    PARTICIPANT
    --------------------------------------------------
    Name: {participant_name}
    Email: {participant_email}
    Role: {ALLOWED_ROLES.get(
        participant_role,
        participant_role
    )}

    MEETING DETAILS
    --------------------------------------------------
    Meeting ID:
    {meeting_id}

    Meeting Link:
    {meeting_link}

    Date:
    {meeting_date.strftime("%d %B %Y")}

    Time:
    {data["time"].strip()}

    Purpose:
    {purpose}

    The meeting has been saved successfully in MongoDB.

    Regards,
    AgriCentre Meeting Centre
    """

        admin_sent = send_email(
            admin_email,
            admin_subject,
            admin_body
        )


    # ============================================================
    # SAVE EMAIL STATUS
    # ============================================================

    if (
        organizer_sent
        and participant_sent
        and admin_sent
    ):

        email_status = "sent"

    elif (
        organizer_sent
        or participant_sent
        or admin_sent
    ):

        email_status = "partial"

    else:

        email_status = "failed"


    db["meetings"].update_one(
        {
            "_id": result.inserted_id
        },
        {
            "$set": {

                "email_status":
                    email_status,

                "organizer_email_sent":
                    organizer_sent,

                "participant_email_sent":
                    participant_sent,

                "admin_email_sent":
                    admin_sent
            }
        }
    )


    # ============================================================
    # RETURN MEETING DETAILS TO FRONTEND
    # ============================================================

    return jsonify({

        "success": True,

        "meeting": {

            "id":
                str(result.inserted_id),

            "meeting_id":
                meeting_id,

            "meeting_link":
                meeting_link,

            "organizer":
                serialize_user(current_user),

            "participant":
                serialize_user(participant),

            "date":
                meeting_date.isoformat(),

            "time":
                data["time"].strip(),

            "purpose":
                purpose,

            "status":
                "scheduled"

        },

        "email_status":
            email_status,

        "emails": {

            "organizer":
                organizer_sent,

            "participant":
                participant_sent,

            "admin":
                admin_sent

        },

        "message":
            (
                "Meeting scheduled successfully. "
                "The Meeting ID and link have been sent."
            )

    }), 201
# ============================================================
# REQUEST AGRICENTRE SUPPORT MEETING
#
# POST /api/meetings/support
# ============================================================

@meeting_bp.route(
    "/api/meetings/support",
    methods=["OPTIONS"],
    provide_automatic_options=False
)
def support_meeting_preflight():

    return "", 204


@meeting_bp.route(
    "/api/meetings/support",
    methods=["POST"],
    provide_automatic_options=False
)
@token_required
def request_support_meeting():

    current_user = get_current_user()

    if not current_user:
        return jsonify({
            "success": False,
            "message": "Current user not found."
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Request body must be valid JSON."
        }), 400

    name = clean_text(
        data.get("name", ""),
        150
    )

    email = clean_text(
        data.get("email", ""),
        200
    )

    issue = clean_text(
        data.get("issue", ""),
        100
    )

    order_id = clean_text(
        data.get("order_id", ""),
        100
    )

    meeting_date = valid_date(
        data.get("date")
    )

    time = clean_text(
        data.get("time", ""),
        10
    )

    description = clean_text(
        data.get("description", ""),
        1000
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not name:
        return jsonify({
            "success": False,
            "message": "Please enter your name."
        }), 400

    if not email or not re.fullmatch(
        r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
        email
    ):
        return jsonify({
            "success": False,
            "message": "Please provide a valid email address."
        }), 400

    if not issue:
        return jsonify({
            "success": False,
            "message": "Please select an issue."
        }), 400

    if not meeting_date:
        return jsonify({
            "success": False,
            "message": "Please provide a valid date."
        }), 400

    if not valid_time(time):
        return jsonify({
            "success": False,
            "message": "Please provide a valid time."
        }), 400

    if len(description) < 3:
        return jsonify({
            "success": False,
            "message": "Please describe your issue."
        }), 400

    # --------------------------------------------------------
    # GENERATE JITSI MEETING
    # --------------------------------------------------------

    meeting_id = generate_meeting_id()
    meeting_link = build_jitsi_link(meeting_id)

    created_at = datetime.now(timezone.utc)

    # --------------------------------------------------------
    # SAVE SUPPORT REQUEST
    # --------------------------------------------------------

    db = get_db()

    support_document = {

        "meeting_id":
            meeting_id,

        "meeting_link":
            meeting_link,

        "user_id":
            current_user["_id"],

        "name":
            name,

        "email":
            email,

        "issue":
            issue,

        "order_id":
            order_id,

        "date":
            meeting_date.isoformat(),

        "time":
            time,

        "description":
            description,

        "status":
            "requested",

        "created_at":
            created_at,

        "email_sent":
            False
    }

    result = db[
        "support_meetings"
    ].insert_one(
        support_document
    )

    # --------------------------------------------------------
    # EMAIL AGRICENTRE TEAM
    # --------------------------------------------------------

    admin_email = (
        current_app.config.get("CONTACT_RECEIVER")
        or current_app.config.get("MAIL_USERNAME")
    )

    admin_sent = False

    if admin_email:

        admin_subject = (
            "AgriCentre Support Meeting Request — "
            + name
        )

        admin_body = f"""
Hello AgriCentre Team,

A new support meeting has been requested.

USER DETAILS
--------------------------------------------------
Name: {name}
Email: {email}
Account ID: {current_user["_id"]}

ISSUE
--------------------------------------------------
Category: {issue}
Related Order ID: {order_id or "Not provided"}

DESCRIPTION
--------------------------------------------------
{description}

MEETING DETAILS
--------------------------------------------------
Meeting ID: {meeting_id}
Meeting Link: {meeting_link}
Date: {meeting_date.strftime("%d %B %Y")}
Time: {time}

The support meeting request has been saved successfully
in MongoDB.

Regards,
AgriCentre Meeting Centre
"""

        admin_sent = send_email(
            admin_email,
            admin_subject,
            admin_body
        )

    # --------------------------------------------------------
    # EMAIL USER
    # --------------------------------------------------------

    user_sent = False

    user_subject = (
        "AgriCentre Support Meeting Request Received"
    )

    user_body = f"""
Hello {name},

Your AgriCentre support meeting request has been received.

MEETING DETAILS
--------------------------------------------------
Meeting ID: {meeting_id}

Meeting Link:
{meeting_link}

Preferred Date:
{meeting_date.strftime("%d %B %Y")}

Preferred Time:
{time}

Issue:
{issue}

Description:
{description}

The AgriCentre support team has been notified of your
request.

Please keep the Meeting ID and link for your meeting.

Regards,
AgriCentre Team
"""

    user_sent = send_email(
        email,
        user_subject,
        user_body
    )

    # --------------------------------------------------------
    # SAVE EMAIL STATUS
    # --------------------------------------------------------

    if admin_sent and user_sent:
        email_status = "sent"

    elif admin_sent or user_sent:
        email_status = "partial"

    else:
        email_status = "failed"

    db["support_meetings"].update_one(
        {
            "_id":
                result.inserted_id
        },
        {
            "$set": {

                "email_status":
                    email_status,

                "email_sent":
                    user_sent,

                "admin_email_sent":
                    admin_sent
            }
        }
    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return jsonify({

        "success": True,

        "message":
            "Support meeting requested successfully.",

        "meeting": {

            "id":
                str(result.inserted_id),

            "meeting_id":
                meeting_id,

            "meeting_link":
                meeting_link,

            "date":
                meeting_date.isoformat(),

            "time":
                time,

            "issue":
                issue
        },

        "email_status":
            email_status,

        "emails": {

            "user":
                user_sent,

            "admin":
                admin_sent
        }

    }), 201
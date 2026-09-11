from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from email.utils import parseaddr
from html import escape
import re

from utils.email_service import send_email


contact_bp = Blueprint(
    "contact",
    __name__
)


# ============================================================
# VALIDATION
# ============================================================

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)


CONTACT_CATEGORIES = {
    "General Query",
    "Technical Support",
    "Feature Query",
    "Partnership",
    "Other"
}


FEEDBACK_CATEGORIES = {
    "Platform Experience",
    "Dashboard",
    "Marketplace",
    "AI Features",
    "Logistics",
    "Other"
}


def clean_text(value, max_length):

    if not isinstance(value, str):
        return ""

    value = " ".join(
        value.strip().split()
    )

    return value[:max_length]


def clean_message(value, max_length=5000):

    if not isinstance(value, str):
        return ""

    return value.strip()[:max_length]


def valid_email(email):

    if not isinstance(email, str):
        return False

    email = email.strip().lower()

    if len(email) > 254:
        return False

    name, address = parseaddr(email)

    return (
        not name
        and address == email
        and EMAIL_PATTERN.fullmatch(email) is not None
    )


# ============================================================
# COMMON VALIDATION
# ============================================================

def validate_common(data):

    if not isinstance(data, dict):

        return None, "Request body must be valid JSON."


    name = clean_text(
        data.get("name"),
        100
    )

    email = str(
        data.get("email", "")
    ).strip().lower()

    message = clean_message(
        data.get("message")
    )


    if not name:

        return None, "Name is required."


    if len(name) < 2:

        return None, "Name must contain at least 2 characters."


    if not valid_email(email):

        return None, "Please enter a valid email address."


    if not message:

        return None, "Message is required."


    if len(message) < 5:

        return None, "Message must contain at least 5 characters."


    return {
        "name": name,
        "email": email,
        "message": message
    }, None


# ============================================================
# TEAM EMAIL
# ============================================================

def build_team_email(
    form_type,
    name,
    email,
    category,
    message
):

    if form_type == "contact":

        title = "New Contact Request"

    else:

        title = "New Feedback Received"


    return f"""
<html>

<body
    style="
        margin:0;
        background:#f4f7f5;
        font-family:Arial,sans-serif;
        color:#24302a;
    "
>

<div
    style="
        max-width:680px;
        margin:30px auto;
        background:#ffffff;
        border:1px solid #e2e8e4;
        border-radius:14px;
        overflow:hidden;
    "
>

    <div
        style="
            background:#174d2b;
            padding:24px 28px;
        "
    >

        <div
            style="
                font-size:13px;
                color:#bde8c9;
                font-weight:bold;
                letter-spacing:.08em;
            "
        >
            AGRICENTRE
        </div>


        <h1
            style="
                margin:7px 0 0;
                color:#ffffff;
                font-size:25px;
            "
        >
            {escape(title)}
        </h1>

    </div>


    <div style="padding:28px;">

        <table
            style="
                width:100%;
                border-collapse:collapse;
                font-size:14px;
            "
        >

            <tr>

                <td
                    style="
                        padding:11px 0;
                        color:#68756d;
                        width:150px;
                    "
                >
                    Name
                </td>

                <td
                    style="
                        padding:11px 0;
                        font-weight:600;
                    "
                >
                    {escape(name)}
                </td>

            </tr>


            <tr>

                <td
                    style="
                        padding:11px 0;
                        color:#68756d;
                    "
                >
                    Email
                </td>

                <td
                    style="
                        padding:11px 0;
                        font-weight:600;
                    "
                >
                    {escape(email)}
                </td>

            </tr>


            <tr>

                <td
                    style="
                        padding:11px 0;
                        color:#68756d;
                    "
                >
                    Category
                </td>

                <td
                    style="
                        padding:11px 0;
                        font-weight:600;
                    "
                >
                    {escape(category)}
                </td>

            </tr>

        </table>


        <div
            style="
                margin-top:22px;
                padding:18px;
                background:#f6faf7;
                border-left:4px solid #2f9e5c;
                border-radius:8px;
            "
        >

            <div
                style="
                    font-size:12px;
                    color:#68756d;
                    font-weight:bold;
                    text-transform:uppercase;
                    margin-bottom:8px;
                "
            >
                Message
            </div>


            <div
                style="
                    white-space:pre-wrap;
                    line-height:1.65;
                    font-size:14px;
                "
            >
                {escape(message)}
            </div>

        </div>


        <div
            style="
                margin-top:24px;
                font-size:12px;
                color:#8a968f;
            "
        >
            Submitted through the AgriCentre public contact page.
        </div>

    </div>

</div>

</body>

</html>
"""


# ============================================================
# USER CONFIRMATION EMAIL
# ============================================================

def build_user_email(
    form_type,
    name,
    category,
    message
):

    if form_type == "contact":

        subject = (
            "We received your message — AgriCentre"
        )

        heading = (
            "Your message has been received"
        )

        intro = (
            "Thank you for contacting AgriCentre. "
            "Our team has received your message and "
            "will get back to you as soon as possible."
        )

        closing = (
            "We appreciate you reaching out to us."
        )

    else:

        subject = (
            "Thank you for your feedback — AgriCentre"
        )

        heading = (
            "Thank you for your feedback"
        )

        intro = (
            "Your feedback has been successfully "
            "submitted to the AgriCentre team. "
            "It helps us improve the platform and "
            "your experience."
        )

        closing = (
            "Thank you for helping us make "
            "AgriCentre better."
        )


    html = f"""
<html>

<body
    style="
        margin:0;
        background:#f4f7f5;
        font-family:Arial,sans-serif;
        color:#24302a;
    "
>

<div
    style="
        max-width:620px;
        margin:30px auto;
        background:#ffffff;
        border:1px solid #e2e8e4;
        border-radius:14px;
        overflow:hidden;
    "
>

    <div
        style="
            background:#174d2b;
            padding:24px 28px;
        "
    >

        <div
            style="
                font-size:13px;
                color:#bde8c9;
                font-weight:bold;
                letter-spacing:.08em;
            "
        >
            AGRICENTRE
        </div>


        <h1
            style="
                margin:8px 0 0;
                color:#ffffff;
                font-size:24px;
            "
        >
            {escape(heading)}
        </h1>

    </div>


    <div style="padding:28px;">

        <p
            style="
                font-size:15px;
                line-height:1.7;
            "
        >
            Hello {escape(name)},
        </p>


        <p
            style="
                font-size:15px;
                line-height:1.7;
            "
        >
            {escape(intro)}
        </p>


        <div
            style="
                margin:22px 0;
                padding:18px;
                background:#f6faf7;
                border-radius:9px;
            "
        >

            <div
                style="
                    font-size:12px;
                    color:#68756d;
                    font-weight:bold;
                    text-transform:uppercase;
                "
            >
                {escape(category)}
            </div>


            <div
                style="
                    margin-top:9px;
                    white-space:pre-wrap;
                    line-height:1.65;
                    font-size:14px;
                "
            >
                {escape(message)}
            </div>

        </div>


        <p
            style="
                font-size:14px;
                line-height:1.7;
            "
        >
            {escape(closing)}
        </p>


        <p
            style="
                margin-top:26px;
                font-size:14px;
            "
        >
            Regards,<br>
            <strong>AgriCentre Team</strong>
        </p>

    </div>

</div>

</body>

</html>
"""


    text = f"""
Hello {name},

{intro}

Category:
{category}

Your message:
{message}

{closing}

Regards,
AgriCentre Team
"""


    return (
        subject,
        text,
        html
    )


# ============================================================
# SEND TEAM + USER EMAIL
# ============================================================

def send_contact_emails(
    form_type,
    name,
    email,
    category,
    message
):

    receiver = (
        current_app.config.get(
            "CONTACT_RECEIVER"
        )
        or current_app.config.get(
            "MAIL_USERNAME"
        )
    )


    if not receiver:

        print(
            "Contact email error: "
            "CONTACT_RECEIVER / MAIL_USERNAME not configured."
        )

        return False, False


    # --------------------------------------------------------
    # EMAIL TO AGRICENTRE TEAM
    # --------------------------------------------------------

    if form_type == "contact":

        team_subject = (
            "New Contact Request — AgriCentre"
        )

    else:

        team_subject = (
            "New Feedback — AgriCentre"
        )


    team_html = build_team_email(
        form_type,
        name,
        email,
        category,
        message
    )


    team_text = f"""
New {'contact request' if form_type == 'contact' else 'feedback'}

Name: {name}
Email: {email}
Category: {category}

Message:
{message}
"""


    team_sent = send_email(
        receiver,
        team_subject,
        team_text,
        html_body=team_html
    )


    # --------------------------------------------------------
    # CONFIRMATION EMAIL TO USER
    # --------------------------------------------------------

    user_subject, user_text, user_html = build_user_email(
        form_type,
        name,
        category,
        message
    )


    user_sent = send_email(
        email,
        user_subject,
        user_text,
        html_body=user_html
    )


    return (
        team_sent,
        user_sent
    )


# ============================================================
# CONTACT
#
# POST /api/contact
# ============================================================

@contact_bp.route(
    "/api/contact",
    methods=["POST", "OPTIONS"]
)
def submit_contact():

    if request.method == "OPTIONS":

        return "", 204


    data = request.get_json(
        silent=True
    )


    common, error = validate_common(
        data
    )


    if error:

        return jsonify({
            "success": False,
            "message": error
        }), 400


    category = str(
        data.get(
            "category",
            ""
        )
    ).strip()


    if category not in CONTACT_CATEGORIES:

        return jsonify({
            "success": False,
            "message": "Please select a valid query type."
        }), 400


    db = current_app.config["DB"]


    document = {
        **common,

        "category": category,

        "type": "contact",

        "status": "pending",

        "created_at":
            datetime.now(timezone.utc),

        "email_status":
            "pending"
    }


    result = db[
        "contact_messages"
    ].insert_one(
        document
    )


    team_sent, user_sent = send_contact_emails(
        "contact",
        common["name"],
        common["email"],
        category,
        common["message"]
    )


    if team_sent and user_sent:

        email_status = "sent"

    elif team_sent or user_sent:

        email_status = "partial"

    else:

        email_status = "failed"


    db[
        "contact_messages"
    ].update_one(
        {
            "_id":
                result.inserted_id
        },
        {
            "$set": {

                "email_status":
                    email_status,

                "team_email_sent":
                    team_sent,

                "user_email_sent":
                    user_sent

            }
        }
    )


    if not team_sent or not user_sent:

        return jsonify({

            "success": False,

            "saved": True,

            "message":
                "Your message was saved, but we could not complete the email notification. Please try again."

        }), 503


    return jsonify({

        "success": True,

        "message":
            "Your message has been sent successfully. A confirmation email has been sent to you."

    }), 201


# ============================================================
# FEEDBACK
#
# POST /api/feedback
# ============================================================

@contact_bp.route(
    "/api/feedback",
    methods=["POST", "OPTIONS"]
)
def submit_feedback():

    if request.method == "OPTIONS":

        return "", 204


    data = request.get_json(
        silent=True
    )


    common, error = validate_common(
        data
    )


    if error:

        return jsonify({
            "success": False,
            "message": error
        }), 400


    category = str(
        data.get(
            "category",
            ""
        )
    ).strip()


    if category not in FEEDBACK_CATEGORIES:

        return jsonify({
            "success": False,
            "message":
                "Please select a valid feedback category."
        }), 400


    db = current_app.config["DB"]


    document = {
        **common,

        "category": category,

        "type": "feedback",

        "status": "pending",

        "created_at":
            datetime.now(timezone.utc),

        "email_status":
            "pending"
    }


    result = db[
        "feedback"
    ].insert_one(
        document
    )


    team_sent, user_sent = send_contact_emails(
        "feedback",
        common["name"],
        common["email"],
        category,
        common["message"]
    )


    if team_sent and user_sent:

        email_status = "sent"

    elif team_sent or user_sent:

        email_status = "partial"

    else:

        email_status = "failed"


    db[
        "feedback"
    ].update_one(
        {
            "_id":
                result.inserted_id
        },
        {
            "$set": {

                "email_status":
                    email_status,

                "team_email_sent":
                    team_sent,

                "user_email_sent":
                    user_sent

            }
        }
    )


    if not team_sent or not user_sent:

        return jsonify({

            "success": False,

            "saved": True,

            "message":
                "Your feedback was saved, but we could not complete the email notification. Please try again."

        }), 503


    return jsonify({

        "success": True,

        "message":
            "Thank you! Your feedback has been submitted successfully. A confirmation email has been sent to you."

    }), 201


from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from email.utils import parseaddr
import re

from utils.email_service import send_email


subscription_bp = Blueprint(
    "subscription",
    __name__
)


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)


def is_valid_email(email):
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


def send_welcome_email(email):
    subject = "Welcome to AgriCentre Updates 🌱"

    body = f"""
Hello,

Thank you for subscribing to AgriCentre updates.

You are now subscribed to receive:
• Important platform updates
• New AgriCentre features
• Agricultural insights
• Relevant announcements

We will only use your email for AgriCentre updates.

Regards,
AgriCentre Team
"""

    return send_email(
        email,
        subject,
        body
    )


def send_team_notification(email):
    receiver = (
        current_app.config.get("CONTACT_RECEIVER")
        or current_app.config.get("MAIL_USERNAME")
    )

    if not receiver:
        return False

    subject = "New AgriCentre Newsletter Subscriber"

    body = f"""
A new visitor subscribed to AgriCentre updates.

Email:
{email}

Subscribed at:
{datetime.now(timezone.utc).isoformat()}
"""

    return send_email(
        receiver,
        subject,
        body
    )


@subscription_bp.route(
    "/api/subscribe",
    methods=["POST", "OPTIONS"]
)
def subscribe():

    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Request body must be valid JSON."
        }), 400

    email = str(
        data.get("email", "")
    ).strip().lower()

    if not is_valid_email(email):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address."
        }), 400

    db = current_app.config["DB"]

    subscribers = db["newsletter_subscribers"]

    existing = subscribers.find_one({
        "email": email
    })

    if existing:
        return jsonify({
            "success": True,
            "already_subscribed": True,
            "message": "This email is already subscribed to AgriCentre updates."
        }), 200

    document = {
        "email": email,
        "status": "active",
        "subscribed_at": datetime.now(timezone.utc)
    }

    subscribers.insert_one(document)

    welcome_sent = send_welcome_email(email)
    team_notified = send_team_notification(email)

    subscribers.update_one(
        {"email": email},
        {
            "$set": {
                "welcome_email_sent": welcome_sent,
                "team_notification_sent": team_notified
            }
        }
    )

    if not welcome_sent:
        return jsonify({
            "success": False,
            "saved": True,
            "message": (
                "Your subscription was saved, but we could not send "
                "the confirmation email. Please try again later."
            )
        }), 503

    return jsonify({
        "success": True,
        "already_subscribed": False,
        "message": (
            "You are now subscribed to AgriCentre updates. "
            "A confirmation email has been sent to you."
        )
    }), 201

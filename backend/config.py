import os
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH)


class Config:
    MONGO_URI = os.getenv("MONGO_URI")
    DB_NAME = os.getenv("DB_NAME", "agricentre")
    JWT_SECRET = os.getenv("JWT_SECRET")
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
    # Replace the email section inside backend/config.py with this:

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))

    # Supports the SENDER_EMAIL/SENDER_PASSWORD names currently in .env.
    MAIL_USERNAME = (
        os.getenv("MAIL_USERNAME")
        or os.getenv("SENDER_EMAIL")
    )

    MAIL_PASSWORD = (
        os.getenv("MAIL_PASSWORD")
        or os.getenv("SENDER_PASSWORD")
    )

    # If CONTACT_RECEIVER is not separately configured, use the AgriCentre
    # mailbox itself as the destination for contact/feedback notifications.
    CONTACT_RECEIVER = (
        os.getenv("CONTACT_RECEIVER")
        or MAIL_USERNAME
    )

import smtplib
from email.message import EmailMessage
from flask import current_app


def send_email(to_email, subject, body, html_body=None):
    """Send a transactional email through the configured SMTP server."""

    try:
        username = current_app.config.get("MAIL_USERNAME")
        password = current_app.config.get("MAIL_PASSWORD")
        server_host = current_app.config.get("MAIL_SERVER", "smtp.gmail.com")
        server_port = int(current_app.config.get("MAIL_PORT", 587))

        if not username or not password:
            print("Email error: MAIL_USERNAME / MAIL_PASSWORD is not configured.")
            return False

        msg = EmailMessage()
        msg["From"] = username
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        if html_body:
            msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(server_host, server_port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(username, password)
            server.send_message(msg)

        return True

    except Exception as e:
        print("Email error:", repr(e))
        return False

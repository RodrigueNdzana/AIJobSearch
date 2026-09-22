"""
Sends transactional email (currently just password-reset). If SMTP isn't
configured (settings.smtp_host is empty), emails are printed to the backend
log instead of sent — this keeps local development and the Docker Compose
setup working out of the box without requiring real mail credentials.

To send real email, set SMTP_HOST/SMTP_PORT/SMTP_USERNAME/SMTP_PASSWORD in
your .env (or docker-compose.yml environment). Any standard SMTP provider
works — Gmail (with an app password), SendGrid, Postmark, AWS SES, etc.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger("app.email")


def send_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> None:
    if not settings.smtp_host:
        # Dev fallback: log it instead of sending. Loud and clearly labeled so
        # it's obvious in the logs that no real email went out.
        logger.warning(
            "SMTP not configured — email NOT sent. Would have sent:\n"
            "  To: %s\n  Subject: %s\n  Body:\n%s",
            to_email, subject, text_body or html_body,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.email_from}>"
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.email_from, [to_email], msg.as_string())


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    subject = "Reset your AI Jobline password"
    text_body = (
        f"We received a request to reset your AI Jobline password.\n\n"
        f"Reset it here (valid for {settings.password_reset_token_expire_minutes} minutes):\n"
        f"{reset_link}\n\n"
        f"If you didn't request this, you can safely ignore this email."
    )
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#1B2430;">Reset your password</h2>
      <p>We received a request to reset your AI Jobline password. This link is
      valid for {settings.password_reset_token_expire_minutes} minutes.</p>
      <p style="margin: 24px 0;">
        <a href="{reset_link}" style="background:#0F6E56; color:#fff; padding:10px 18px;
           border-radius:3px; text-decoration:none; font-weight:600;">Reset password</a>
      </p>
      <p style="color:#666; font-size:0.85em;">
        If the button doesn't work, copy and paste this link into your browser:<br>
        {reset_link}
      </p>
      <p style="color:#666; font-size:0.85em;">
        If you didn't request this, you can safely ignore this email.
      </p>
    </div>
    """
    send_email(to_email, subject, html_body, text_body)

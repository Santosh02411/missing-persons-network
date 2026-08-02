import logging
<<<<<<< HEAD
import smtplib
from email.message import EmailMessage

from app.core.config import settings
=======
>>>>>>> 0a84c8b8037ce65b90f512ff6a732d74ee3d7e30

logger = logging.getLogger("app.email")


<<<<<<< HEAD
def _send_console(to: str, subject: str, body: str) -> None:
    """Default backend -- no setup required. Check the API container's logs
    (`docker compose logs -f api`) to see verification and password-reset
    links during local development."""
    logger.info(
        "=== EMAIL (console -- not actually sent) ===\nTo: %s\nSubject: %s\n\n%s\n=============================================",
=======
def send_email(to: str, subject: str, body: str) -> None:
    """Stub email sender. This project has no SMTP/email provider configured,
    so this just logs the message instead of sending it -- check the API
    container's logs (`docker compose logs -f api`) to see verification and
    password-reset links during local development.

    Swap this out for a real provider (SendGrid, AWS SES, Postmark, etc.)
    before this goes anywhere near real users. Every call site that needs to
    send an email already goes through this one function, so it's the only
    place that needs to change.
    """
    logger.info(
        "=== EMAIL (stub — not actually sent) ===\nTo: %s\nSubject: %s\n\n%s\n=========================================",
>>>>>>> 0a84c8b8037ce65b90f512ff6a732d74ee3d7e30
        to,
        subject,
        body,
    )
<<<<<<< HEAD


def _send_smtp(to: str, subject: str, body: str) -> None:
    """Sends a real email via SMTP. Requires SMTP_HOST/PORT/USERNAME/PASSWORD/
    FROM_EMAIL to be set (see .env.example for a Gmail App Password
    walkthrough). Any failure is logged, not raised -- a broken email
    provider shouldn't crash registration or password reset; the person can
    still use the app, they just won't get the email."""
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        logger.error(
            "EMAIL_BACKEND=smtp but SMTP_HOST/SMTP_FROM_EMAIL aren't set -- "
            "falling back to console. Fill in the SMTP_* settings in .env."
        )
        _send_console(to, subject, body)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Sent email to %s: %s", to, subject)
    except Exception:
        logger.exception("Failed to send email to %s via SMTP", to)


def send_email(to: str, subject: str, body: str) -> None:
    """Single choke point for all outbound email in this app (verification,
    password reset) -- swap EMAIL_BACKEND in .env to change how it's sent,
    nothing else in the codebase needs to change."""
    if settings.EMAIL_BACKEND == "smtp":
        _send_smtp(to, subject, body)
    else:
        _send_console(to, subject, body)
=======
>>>>>>> 0a84c8b8037ce65b90f512ff6a732d74ee3d7e30

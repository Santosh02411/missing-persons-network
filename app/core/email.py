import logging

logger = logging.getLogger("app.email")


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
        to,
        subject,
        body,
    )

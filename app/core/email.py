import logging
import mimetypes
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("app.email")


def _send_console(to: str, subject: str, body: str, attachments: list[tuple[str, bytes]] | None = None) -> None:
    """Default backend -- no setup required. Check the API container's logs
    (`docker compose logs -f api`) to see verification and password-reset
    links during local development."""
    attachment_note = ""
    if attachments:
        names = ", ".join(name for name, _ in attachments)
        attachment_note = f"\n[{len(attachments)} attachment(s): {names}]"
    logger.info(
        "=== EMAIL (console -- not actually sent) ===\nTo: %s\nSubject: %s\n\n%s%s\n=============================================",
        to,
        subject,
        body,
        attachment_note,
    )


def _send_smtp(
    to: str, subject: str, body: str, attachments: list[tuple[str, bytes]] | None = None
) -> None:
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
        _send_console(to, subject, body, attachments)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to
    msg.set_content(body)

    for filename, content in attachments or []:
        content_type, _ = mimetypes.guess_type(filename)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

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


def send_email(
    to: str, subject: str, body: str, attachments: list[tuple[str, bytes]] | None = None
) -> None:
    """Single choke point for all outbound email in this app (verification,
    password reset, case sharing) -- swap EMAIL_BACKEND in .env to change how
    it's sent, nothing else in the codebase needs to change.

    `attachments` is a list of (filename, raw_bytes) tuples -- used by
    case_service.share_case to send the case photo as a "soft copy"
    alongside the case details in the email body.
    """
    if settings.EMAIL_BACKEND == "smtp":
        _send_smtp(to, subject, body, attachments)
    else:
        _send_console(to, subject, body, attachments)
